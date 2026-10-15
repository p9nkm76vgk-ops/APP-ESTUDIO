"""Construcción de las instrucciones para la IA y generación del material."""
from __future__ import annotations

import re

from .config import Subject, load_output_types, load_prompt
from .providers import Provider

LANG_NAMES = {"es": "castellano", "ca": "catalán", "en": "inglés"}
MAX_SOURCE_CHARS = 120_000  # por encima, se avisa y se recorta (o se procesa por partes en el futuro)


def _bullets(items) -> str:
    return "\n".join(f"- {i}" for i in items) if items else "- (sin indicaciones)"


def build_system_prompt(subject: Subject, kind: str, corrections: list[str] | None = None) -> str:
    method = load_prompt("metodo_apuntes.md")
    method = method.replace("{{asignatura}}", subject.name).replace("{{idioma}}", LANG_NAMES.get(subject.language, subject.language))
    types = load_output_types()
    sel = subject.selection or {}
    parts = [
        method,
        f"\n## Asignatura: {subject.name}\n",
        "### Qué se prioriza\n" + _bullets(subject.focus),
        "### Estructura de los apuntes\n" + _bullets(subject.structure),
        "### Qué conservar\n" + _bullets(sel.get("keep")),
        "### Qué descartar o condensar\n" + _bullets(sel.get("drop")),
        "### Qué avisar\n" + _bullets(sel.get("flag")),
        "### Tipos de ejercicios\n" + _bullets(subject.exercise_types),
        "### Criterios de calidad\n" + _bullets(subject.quality),
        f"\n## Tipo de material pedido: {kind}\n{types.get(kind, '')}",
    ]
    if corrections:
        parts.append("## Correcciones del alumno que debes respetar\n" + _bullets(corrections))
    return "\n\n".join(parts)


def build_user_prompt(source_text: str, title: str, kind: str, extra: str = "") -> tuple[str, bool]:
    truncated = len(source_text) > MAX_SOURCE_CHARS
    text = source_text[:MAX_SOURCE_CHARS]
    msg = (
        f"<titulo>{title}</titulo>\n<tipo>{kind}</tipo>\n"
        "Este es el documento original que me ha dado mi profesora. Hazme el material pedido "
        "siguiendo todas las instrucciones.\n"
        f"<documento>\n{text}\n</documento>"
    )
    if extra:
        msg += f"\n\nIndicaciones adicionales del alumno: {extra}"
    return msg, truncated


def generate(provider: Provider, subject: Subject, source_text: str, title: str, kind: str,
             corrections: list[str] | None = None, extra: str = "", max_tokens: int = 8000) -> tuple[str, list[str]]:
    system = build_system_prompt(subject, kind, corrections)
    user, truncated = build_user_prompt(source_text, title, kind, extra)
    warnings = []
    if truncated:
        warnings.append("El documento es muy largo y se ha recortado. Divídelo en partes para no perder contenido.")
    md = provider.generate(system, user, max_tokens=max_tokens).strip()
    if not md.startswith("#"):
        md = f"# {title}\n\n{md}"
    return md, warnings


# ---------- Secciones (para regenerar una parte sin rehacer todo) ----------

SECTION_RE = re.compile(r"^## .*$", re.M)


def list_sections(md: str) -> list[str]:
    return [m.group(0)[3:].strip() for m in SECTION_RE.finditer(md)]


def get_section(md: str, heading: str) -> tuple[int, int] | None:
    matches = list(SECTION_RE.finditer(md))
    for i, m in enumerate(matches):
        if m.group(0)[3:].strip() == heading:
            end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
            return m.start(), end
    return None


def regenerate_section(provider: Provider, subject: Subject, md: str, heading: str, source_text: str,
                       instruction: str = "", corrections: list[str] | None = None) -> str:
    span = get_section(md, heading)
    if span is None:
        raise ValueError(f"No existe la sección «{heading}».")
    if not provider.uses_ai:
        raise ValueError("Regenerar una sección necesita la IA (configura la clave de la API).")
    current = md[span[0]:span[1]].strip()
    system = build_system_prompt(subject, "apuntes", corrections)
    user = (
        "Reescribe SOLO esta sección de mis apuntes, manteniendo el título «## " + heading + "». "
        "Devuelve únicamente la sección en Markdown.\n"
        f"<seccion_actual>\n{current}\n</seccion_actual>\n"
        f"<documento>\n{source_text[:MAX_SOURCE_CHARS]}\n</documento>"
    )
    if instruction:
        user += f"\nQué quiero cambiar: {instruction}"
    new = provider.generate(system, user, max_tokens=4000).strip()
    if not new.startswith("## "):
        new = f"## {heading}\n\n{new}"
    return md[:span[0]] + new + "\n\n" + md[span[1]:].lstrip()
