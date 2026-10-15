"""Adaptador de Goodnotes, separado de la exportación.

Estado comprobado (15/10/2026):
- No hay API pública de Goodnotes: existe una petición de usuarios en su foro (abril de 2026)
  sin respuesta oficial. https://feedback.goodnotes.com/forums/191274/suggestions/51189895
- El conector de Goodnotes en Claude tiene 3 herramientas (texto Markdown, diagrama Mermaid,
  dibujo SVG). Probado: devuelve un widget en el chat que se puede pasar a Goodnotes
  desde iOS/macOS. Solo crea documentos nuevos desde una conversación: no importa PDF,
  no crea ni elige carpetas, no actualiza ni lee documentos, y una app externa no puede usarlo.

Por eso la mejor alternativa práctica es: PDF con nombre consistente + importación manual
(compartir desde Archivos/Safari → Goodnotes, o arrastrar al iPad). Si en el futuro
aparece un mecanismo oficial, solo hay que implementar `push()` aquí.
"""
from __future__ import annotations

from .config import Subject
from .storage import safe_name

CAPABILITIES = {
    "api_oficial": False,
    "importar_automaticamente": False,
    "crear_carpetas": False,
    "actualizar_documentos": False,
    "detectar_duplicados": False,
    "conector_claude": "Crea documentos nuevos (Markdown/diagramas) desde el chat; sin PDF, carpetas ni actualizaciones.",
}


def filename_for(subject: Subject, topic: str, kind_label: str, version: int) -> str:
    """Nombre estable para que en Goodnotes se vea ordenado y se distingan versiones."""
    return safe_name(f"{subject.folder[:2]} {subject.name} - {topic} - {kind_label} - v{version}", 150) + ".pdf"


def import_instructions(subject: Subject) -> list[str]:
    return [
        f"En Goodnotes, crea (una sola vez) la carpeta «{subject.folder}».",
        "Descarga el PDF desde la app (botón PDF) en el iPad.",
        "Ábrelo, pulsa Compartir y elige Goodnotes → «Importar como documento nuevo».",
        f"Elige la carpeta «{subject.folder}». Si es una versión nueva, borra o archiva la anterior.",
    ]


def push(*_args, **_kwargs):
    raise NotImplementedError("Goodnotes no ofrece un mecanismo oficial de importación automática.")
