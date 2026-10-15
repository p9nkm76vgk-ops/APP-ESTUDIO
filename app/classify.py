"""Clasificación de asignatura, idioma y tema.

Es un clasificador transparente basado en palabras clave editables (config/subjects/*.yaml)
más el idioma del texto. Devuelve una confianza y avisa si el documento parece mezclar
asignaturas. Si hay un proveedor de IA, se puede usar para desempatar (ver pipeline).
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field

from .config import Subject

STOPWORDS = {
    "es": {"el", "la", "los", "las", "de", "que", "y", "en", "un", "una", "por", "con", "para", "del", "se", "su", "es", "como", "más", "pero", "sus", "le", "ya", "o", "este", "sí", "porque", "esta", "entre", "cuando", "muy", "sin", "sobre", "también", "me", "hasta", "hay", "donde", "quien", "desde", "todo", "nos", "durante", "todos", "uno", "les", "ni", "contra", "otros", "ese", "eso", "ante", "ellos", "e", "esto", "mí", "antes", "algunos", "qué", "unos", "yo", "otro", "otras", "otra", "él", "tanto", "esa", "estos", "mucho", "quienes", "nada", "muchos", "cual", "poco", "ella", "estar", "estas", "algunas", "algo", "nosotros"},
    "ca": {"el", "la", "els", "les", "de", "que", "i", "en", "un", "una", "per", "amb", "del", "es", "seu", "seva", "com", "més", "però", "ja", "o", "aquest", "aquesta", "perquè", "entre", "quan", "molt", "sense", "sobre", "també", "fins", "hi", "on", "qui", "des", "tot", "ens", "durant", "tots", "dels", "als", "al", "ni", "contra", "altres", "això", "davant", "ells", "aquests", "algun", "què", "uns", "jo", "altre", "altra", "ell", "tant", "aquestes", "molts", "cap", "poc", "ella", "estar", "algunes", "alguna", "nosaltres", "és", "són", "va", "fou", "seus", "seves", "aquell", "aquella", "tenim", "trobam", "podem", "hem", "dir"},
    "en": {"the", "of", "and", "to", "in", "a", "is", "that", "for", "it", "as", "was", "with", "be", "by", "on", "not", "he", "this", "are", "or", "his", "from", "at", "which", "but", "have", "an", "they", "you", "were", "their", "one", "all", "we", "can", "has", "there", "been", "if", "more", "when", "will", "would", "who", "so", "no"},
}


@dataclass
class Classification:
    subject_id: str | None
    confidence: float
    language: str
    topic: str
    scores: dict[str, float] = field(default_factory=dict)
    matched: dict[str, list[str]] = field(default_factory=dict)
    mixed_with: list[str] = field(default_factory=list)
    needs_review: bool = False
    reason: str = ""


def _strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def detect_language(text: str) -> str:
    words = re.findall(r"[a-zà-ÿ·']+", text.lower())
    if not words:
        return "es"
    counts = {lang: sum(1 for w in words if w in sw) for lang, sw in STOPWORDS.items()}
    # Palabras muy distintivas del catalán
    counts["ca"] += 3 * sum(1 for w in words if w in {"els", "amb", "però", "perquè", "això", "aquesta", "també", "seva", "fou", "és"})
    counts["es"] += 3 * sum(1 for w in words if w in {"los", "con", "pero", "porque", "esto", "también", "fue", "sus", "muy", "hay"})
    return max(counts, key=counts.get)


def detect_topic(text: str, filename: str = "") -> str:
    """Primer título razonable del documento; si no hay, el nombre del archivo."""
    for line in text.splitlines()[:15]:
        t = line.strip().strip("#").strip()
        if 3 <= len(t) <= 80 and not re.match(r"^(p\.|pág|page)\s*\d+", t, re.I) and not t[0].isdigit():
            t = t.rstrip(" .:;")
            return _nice_case(t) if t.isupper() else t
    stem = re.sub(r"[_\-]+", " ", filename.rsplit(".", 1)[0]).strip()
    return stem or "Sin título"


SMALL_WORDS = {"de", "del", "la", "las", "el", "los", "y", "e", "i", "en", "a", "al", "les", "els", "per", "con", "amb", "of", "the", "and"}


def _nice_case(t: str) -> str:
    """«POEMA RETRATO DE MACHADO» -> «Poema Retrato de Machado»; siglas de 2 letras se mantienen."""
    words = t.split()
    out = []
    for i, w in enumerate(words):
        lw = w.lower()
        if i and lw in SMALL_WORDS:
            out.append(lw)
        elif len(w) <= 2 and i:
            out.append(w)  # SE, II...
        else:
            out.append(w.capitalize())
    return " ".join(out)


def _count(keyword: str, text_norm: str) -> int:
    kw = _strip_accents(keyword.lower())
    return len(re.findall(r"(?<![a-z0-9])" + re.escape(kw) + r"(?![a-z0-9])", text_norm))


def classify(text: str, subjects: dict[str, Subject], filename: str = "", min_confidence: float = 0.55) -> Classification:
    language = detect_language(text)
    topic = detect_topic(text, filename)
    text_norm = _strip_accents(text.lower())

    scores: dict[str, float] = {}
    matched: dict[str, list[str]] = {}
    for sid, s in subjects.items():
        score, hits = 0.0, []
        for kw in s.keywords:
            n = _count(kw, text_norm)
            if n:
                hits.append(kw)
                score += 1 + math.log(n)
        if s.language_bonus and s.language_bonus == language and hits:
            score += 3.0
        scores[sid], matched[sid] = round(score, 2), hits

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (top_id, top), (second_id, second) = ranked[0], ranked[1]

    if top < 2:
        return Classification(None, 0.0, language, topic, scores, matched, needs_review=True,
                              reason="No hay suficientes indicios para decidir la asignatura.")

    strength = min(1.0, top / 10)
    separation = 1 - second / top
    confidence = round(strength * (0.4 + 0.6 * separation), 2)

    mixed = [sid for sid, sc in ranked[1:] if sc >= 4 and sc >= 0.6 * top]
    needs_review = confidence < min_confidence or bool(mixed)
    if mixed:
        reason = "El documento parece contener material de varias asignaturas."
    elif needs_review:
        reason = "La clasificación es dudosa; confirma la asignatura antes de guardar."
    else:
        reason = "Clasificación fiable."
    return Classification(top_id, confidence, language, topic, scores, matched, mixed, needs_review, reason)
