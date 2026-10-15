"""Carga de la configuración editable (YAML) de la app y de las asignaturas."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
PROMPTS_DIR = ROOT / "prompts"


@dataclass
class Subject:
    id: str
    name: str
    folder: str
    language: str
    design: dict
    focus: list = field(default_factory=list)
    structure: list = field(default_factory=list)
    selection: dict = field(default_factory=dict)
    exercise_types: list = field(default_factory=list)
    quality: list = field(default_factory=list)
    classifier: dict = field(default_factory=dict)

    @property
    def keywords(self) -> list[str]:
        return [k.lower() for k in self.classifier.get("keywords", [])]

    @property
    def language_bonus(self) -> str | None:
        return self.classifier.get("language_bonus")


def _read_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_app_config() -> dict:
    cfg = _read_yaml(CONFIG_DIR / "app.yaml")
    data_dir = Path(os.environ.get("ESTUDIO_DATA_DIR", cfg.get("data_dir", "./data/Sistema-de-Estudio")))
    if not data_dir.is_absolute():
        data_dir = (ROOT / data_dir).resolve()
    cfg["data_dir"] = data_dir
    return cfg


def load_subjects() -> dict[str, Subject]:
    subjects: dict[str, Subject] = {}
    for path in sorted((CONFIG_DIR / "subjects").glob("*.yaml")):
        raw = _read_yaml(path)
        allowed = Subject.__dataclass_fields__.keys()
        s = Subject(**{k: v for k, v in raw.items() if k in allowed})
        subjects[s.id] = s
    return subjects


def load_prompt(name: str) -> str:
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


def load_output_types() -> dict[str, str]:
    return _read_yaml(PROMPTS_DIR / "tipos_salida.yaml")
