"""Modo sin IA: borrador extractivo y fiel.

No resume con inteligencia: reorganiza el texto original por apartados, lo convierte en
listas de frases cortas y genera preguntas de recuperación a partir de los títulos.
Sirve para probar el flujo completo sin clave de API y como red de seguridad.
Todo lo que produce sale literalmente del documento, así que no inventa datos.
"""
from __future__ import annotations

import re

from .base import Provider

BULLET_RE = re.compile(r"^\s*(?:[-•●○■▪–]|\d+\s*[.)]\s+(?=[a-záéíóúàèòç]))\s*")
HEADING_NUM_RE = re.compile(r"^\s*(\d{1,2})\s*[.)]\s*([A-ZÀ-ÚÇ¿¡«].{2,90})$")
SENT_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+(?=[A-ZÀ-ÚÇ«\"“¿¡(])")


def _is_heading(line: str) -> bool:
    t = line.strip()
    if not t or len(t) > 95:
        return False
    if HEADING_NUM_RE.match(t):
        return True
    letters = [c for c in t if c.isalpha()]
    return len(letters) >= 4 and t.upper() == t and len(t.split()) <= 9 and not t.endswith(",")


def _sentence_case(t: str) -> str:
    """«SE VARIANTE DE LE/LES» -> «SE variante de le/les» (las siglas de 2 letras se mantienen)."""
    words = t.split()
    out = [w if (len(w) <= 2 and w.isupper() and i > 0) or (i == 0 and len(w) <= 2) else w.lower()
           for i, w in enumerate(words)]
    s = " ".join(out)
    return s[:1].upper() + s[1:]


def _clean_heading(line: str) -> str:
    t = line.strip().rstrip(".:")
    m = HEADING_NUM_RE.match(t)
    num, text = (m.group(1), m.group(2).rstrip(".:")) if m else (None, t)
    if text.isupper():
        text = _sentence_case(text)
    return f"{num}. {text}" if num else text


def split_sections(text: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    title, lines = "Contenido", []
    for raw in text.splitlines():
        if _is_heading(raw):
            if lines or sections:
                sections.append((title, lines))
            title, lines = _clean_heading(raw), []
        else:
            lines.append(raw)
    sections.append((title, lines))
    return [(t, l) for t, l in sections if any(x.strip() for x in l)]


def to_bullets(lines: list[str]) -> list[str]:
    """Une líneas cortadas del PDF, respeta viñetas del original y parte en frases."""
    blocks, current = [], ""
    for raw in lines:
        line = raw.strip()
        if not line:
            if current:
                blocks.append(current)
                current = ""
            continue
        if BULLET_RE.match(line):
            if current:
                blocks.append(current)
            current = BULLET_RE.sub("", line)
        else:
            current = f"{current} {line}".strip() if current else line
    if current:
        blocks.append(current)

    bullets = []
    for b in blocks:
        b = re.sub(r"\s+", " ", b).strip()
        for s in SENT_SPLIT_RE.split(b):
            s = s.strip()
            if len(s) > 2:
                bullets.append(s)
    return bullets


class OfflineProvider(Provider):
    name = "offline"
    uses_ai = False

    def generate(self, system: str, user: str, max_tokens: int = 8000) -> str:
        doc = re.search(r"<documento>\n?(.*?)\n?</documento>", user, re.S)
        text = doc.group(1) if doc else user
        title_m = re.search(r"<titulo>(.*?)</titulo>", user, re.S)
        title = title_m.group(1).strip() if title_m else "Apuntes"
        kind_m = re.search(r"<tipo>(.*?)</tipo>", user, re.S)
        kind = kind_m.group(1).strip() if kind_m else "apuntes"

        sections = split_sections(text)
        out = [f"# {title}", "",
               "> **Borrador sin IA.** Este documento reorganiza el texto original por apartados, "
               "sin resumirlo ni reescribirlo. Para obtener apuntes simplificados como los de "
               "referencia, configura la clave de la API.", ""]

        if kind == "tarjetas":
            out += ["| Pregunta | Respuesta |", "| --- | --- |"]
            for heading, lines in sections:
                bullets = to_bullets(lines)
                if bullets:
                    out.append(f"| ¿Qué sabes de «{heading}»? | {bullets[0].replace('|', '/')} |")
            return "\n".join(out)

        limit = 3 if kind in ("resumen", "esquema") else None
        for heading, lines in sections:
            bullets = to_bullets(lines)
            if not bullets:
                continue
            out += [f"## {heading}", ""]
            for b in bullets[:limit]:
                out.append(f"- {b}")
            if limit and len(bullets) > limit:
                out.append(f"- *(… {len(bullets) - limit} frases más en el original)*")
            out.append("")

        out += ["## Preguntas de recuperación", "",
                "Contesta sin mirar los apuntes y después comprueba.", ""]
        for i, (heading, _) in enumerate(sections[:10], start=1):
            out.append(f"{i}. Explica con tus palabras: «{heading}».")
        return "\n".join(out)
