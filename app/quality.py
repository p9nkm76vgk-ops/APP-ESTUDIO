"""Control de calidad automático.

Cada comprobación devuelve un estado:
  ok              -> comprobado automáticamente y correcto
  aviso           -> comprobado y hay algo que revisar
  no_verificable  -> no se puede comprobar de forma automática; requiere revisión manual
La app nunca marca como «ok» algo que no ha comprobado.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import asdict, dataclass

from .providers.offline import split_sections


@dataclass
class Check:
    id: str
    name: str
    status: str
    detail: str


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Palabras de la plantilla que pueden aparecer en mayúscula sin estar en el original
TEMPLATE_WORDS = {
    "preguntas", "recuperacion", "respuestas", "soluciones", "ejercicios", "ejemplo", "chuleta",
    "repaso", "conclusion", "asi", "escribiria", "examen", "truco", "nota", "aviso", "borrador",
    "importante", "estrofa", "pregunta", "tema", "identificacion", "contexto", "metrica", "tabla",
    "preguntes", "recuperacio", "exercicis", "conclusio", "aixi", "escriuria", "compte", "idea",
    "clave", "pasos", "parte", "partes", "seccion", "apartado", "resumen", "esquema", "tarjetas",
    "influencia", "influencies", "caracteristicas", "caracteristiques", "interpretacio", "interpretacion",
    "figures", "figuras", "lenguaje", "llenguatge", "biografic", "historic", "contesta", "explica",
    "explicalo", "comprueba", "intenta", "recuerda", "como", "que", "por", "para", "los", "las", "el", "la",
}


def unsupported_terms(output: str, source: str) -> tuple[list[str], list[str]]:
    """Números y nombres propios del resultado que no aparecen en el original."""
    src = _norm(source)
    lines = [l for l in output.splitlines() if "añadid" not in l.lower() and "afegit" not in l.lower()]
    # La numeración de listas y títulos («10.», «## 3.») no son datos
    text = "\n".join(re.sub(r"^\s*(#+\s*)?\d+[.)]\s", " ", l) for l in lines)

    numbers = sorted({n for n in re.findall(r"(?<![\w.])\d{2,4}(?![\w])", text) if n not in src})

    names = set()
    for m in re.finditer(r"(?<![.!?¿¡:\n#>|*-]\s)(?<=\s)([A-ZÁÉÍÓÚÀÈÒÏÜÇÑ][a-záéíóúàèòïüçñ·'-]{3,})", text):
        w = m.group(1)
        nw = _norm(w)
        if nw in TEMPLATE_WORDS:
            continue
        if nw not in src:
            names.add(w)
    return numbers, sorted(names)


def run_checks(output: str, source: str, subject_language: str, detected_output_language: str,
               provider_uses_ai: bool) -> list[dict]:
    checks: list[Check] = []

    nums, names = unsupported_terms(output, source)
    if nums or names:
        detail = "Revisa si estos datos están en el original o los ha añadido la IA: "
        detail += ", ".join(nums + names[:25])
        checks.append(Check("fidelidad", "Datos no encontrados en el original", "aviso", detail))
    else:
        checks.append(Check("fidelidad", "Datos no encontrados en el original", "ok",
                            "Todos los números y nombres propios del resultado aparecen en el original."))

    src_sections = [h for h, _ in split_sections(source) if h != "Contenido"]
    out_norm = _norm(output)
    missing = []
    for h in src_sections:
        words = [w for w in re.findall(r"[a-záéíóúàèòïüçñ·]{5,}", _norm(h))]
        if words and not any(w in out_norm for w in words):
            missing.append(h)
    if not src_sections:
        checks.append(Check("cobertura", "Apartados del original", "no_verificable",
                            "El original no tiene apartados reconocibles; compara a mano."))
    elif missing:
        checks.append(Check("cobertura", "Apartados del original", "aviso",
                            "Puede faltar: " + "; ".join(missing[:10])))
    else:
        checks.append(Check("cobertura", "Apartados del original", "ok",
                            f"Los {len(src_sections)} apartados detectados en el original aparecen en el resultado."))

    has_retrieval = bool(re.search(r"^##+ .*(pregunt|recuper|retrieval|question)", output, re.I | re.M))
    checks.append(Check("recuperacion", "Preguntas de recuperación", "ok" if has_retrieval else "aviso",
                        "Incluye preguntas para practicar sin mirar." if has_retrieval
                        else "No hay sección de preguntas de recuperación: releer no basta para aprender."))

    if subject_language and detected_output_language != subject_language:
        checks.append(Check("idioma", "Idioma de la asignatura", "aviso",
                            f"El resultado parece estar en «{detected_output_language}» y la asignatura usa «{subject_language}»."))
    else:
        checks.append(Check("idioma", "Idioma de la asignatura", "ok", "El idioma coincide con la asignatura."))

    long_sent = [s for s in re.split(r"(?<=[.!?])\s+", re.sub(r"[#>*|\-]", " ", output)) if len(s.split()) > 40]
    checks.append(Check("legibilidad", "Frases largas", "aviso" if len(long_sent) > 3 else "ok",
                        f"{len(long_sent)} frases de más de 40 palabras." if long_sent else "Sin frases excesivamente largas."))

    checks.append(Check("formulas", "Fórmulas, operaciones y unidades", "no_verificable",
                        "La app no comprueba cálculos automáticamente todavía; revísalos a mano."))
    checks.append(Check("pedagogia", "Adecuación a la asignatura y calidad didáctica", "no_verificable",
                        "Requiere tu revisión: compara con los apuntes de referencia."))
    if not provider_uses_ai:
        checks.append(Check("modo", "Modo de generación", "aviso",
                            "Generado sin IA: es un borrador extractivo del original, no unos apuntes simplificados."))
    return [asdict(c) for c in checks]


def summary(checks: list[dict]) -> str:
    if any(c["status"] == "aviso" for c in checks):
        return "revisar"
    return "ok"
