"""Organización de archivos, metadatos, versiones, duplicados e historial.

Estructura en disco (fuera del código y excluida de git):

  data/Sistema-de-Estudio/
    01-Lengua-Castellana/
      Apuntes-Originales/   <- copia del archivo subido
      Apuntes/ Resumenes/ Esquemas/ Preguntas-de-Examen/ Tarjetas/
        <Tema> - <Tipo>.md          <- versión actual (editable)
        <Tema> - <Tipo>.pdf/.html   <- exportaciones
        <Tema> - <Tipo>.meta.json   <- metadatos
        .versiones/<Tema> - <Tipo>.v1.md
    ...
    _sistema/index.json, historial.jsonl, correcciones.jsonl
"""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import threading
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .config import Subject

_lock = threading.Lock()


def now() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_name(s: str, max_len: int = 80) -> str:
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[\\/:*?\"<>|\n\r\t]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" .")
    return (s[:max_len].rstrip() or "Documento")


class Storage:
    def __init__(self, root: Path, subjects: dict[str, Subject], subfolders: dict[str, str]):
        self.root = Path(root)
        self.subjects = subjects
        self.subfolders = subfolders
        self.sys_dir = self.root / "_sistema"
        self.index_path = self.sys_dir / "index.json"
        self.history_path = self.sys_dir / "historial.jsonl"
        self.corrections_path = self.sys_dir / "correcciones.jsonl"
        self.ensure_tree()

    # ---------- estructura ----------
    def ensure_tree(self) -> None:
        self.sys_dir.mkdir(parents=True, exist_ok=True)
        for s in self.subjects.values():
            for sub in self.subfolders.values():
                (self.root / s.folder / sub).mkdir(parents=True, exist_ok=True)
        if not self.index_path.exists():
            self._write_index({"documents": {}, "sources": {}})

    def subject_dir(self, subject_id: str) -> Path:
        return self.root / self.subjects[subject_id].folder

    # ---------- índice ----------
    def _read_index(self) -> dict:
        return json.loads(self.index_path.read_text(encoding="utf-8"))

    def _write_index(self, idx: dict) -> None:
        tmp = self.index_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(idx, ensure_ascii=False, indent=1), encoding="utf-8")
        tmp.replace(self.index_path)

    def log(self, event: str, **data) -> None:
        with _lock, open(self.history_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"fecha": now(), "evento": event, **data}, ensure_ascii=False) + "\n")

    def history(self, limit: int = 200) -> list[dict]:
        if not self.history_path.exists():
            return []
        lines = self.history_path.read_text(encoding="utf-8").splitlines()[-limit:]
        return [json.loads(l) for l in reversed(lines)]

    # ---------- duplicados ----------
    def find_duplicate(self, source_hash: str, kind: str) -> dict | None:
        idx = self._read_index()
        for doc in idx["documents"].values():
            if doc["source_hash"] == source_hash and doc["kind"] == kind:
                return doc
        return None

    def known_source(self, source_hash: str) -> dict | None:
        return self._read_index()["sources"].get(source_hash)

    # ---------- guardar ----------
    def save_original(self, subject_id: str, filename: str, data: bytes, source_hash: str) -> Path:
        with _lock:
            idx = self._read_index()
            if source_hash in idx["sources"]:
                p = self.root / idx["sources"][source_hash]["path"]
                if p.exists():
                    return p
            folder = self.subject_dir(subject_id) / self.subfolders["original"]
            target = folder / safe_name(filename, 120)
            if target.exists() and sha256_bytes(target.read_bytes()) != source_hash:
                target = folder / f"{target.stem} ({source_hash[:6]}){target.suffix}"
            target.write_bytes(data)
            idx["sources"][source_hash] = {"path": str(target.relative_to(self.root)), "filename": filename,
                                           "subject": subject_id, "fecha": now()}
            self._write_index(idx)
            return target

    def save_document(self, *, subject_id: str, kind: str, topic: str, markdown: str, meta: dict,
                      doc_id: str | None = None) -> dict:
        """Crea o actualiza un documento. Si ya existe, guarda la versión anterior."""
        with _lock:
            idx = self._read_index()
            existing = idx["documents"].get(doc_id) if doc_id else None
            if existing:
                md_path = self.root / existing["path"]
                version = existing["version"] + 1
                vdir = md_path.parent / ".versiones"
                vdir.mkdir(exist_ok=True)
                if md_path.exists():
                    shutil.copy2(md_path, vdir / f"{md_path.stem}.v{existing['version']}.md")
            else:
                doc_id = uuid.uuid4().hex[:12]
                version = 1
                folder = self.subject_dir(subject_id) / self.subfolders[kind]
                base = safe_name(f"{topic} - {kind.capitalize()}")
                md_path = folder / f"{base}.md"
                n = 2
                while md_path.exists():
                    md_path = folder / f"{base} ({n}).md"
                    n += 1

            md_path.write_text(markdown, encoding="utf-8")
            record = {
                **(existing or {}), **meta,
                "id": doc_id, "subject": subject_id, "kind": kind, "topic": topic,
                "path": str(md_path.relative_to(self.root)), "version": version,
                "updated": now(), "md_hash": sha256_bytes(markdown.encode("utf-8")),
            }
            record.setdefault("created", record["updated"])
            record.setdefault("status", "borrador")
            idx["documents"][doc_id] = record
            self._write_index(idx)
            (md_path.with_suffix(".meta.json")).write_text(json.dumps(record, ensure_ascii=False, indent=1), encoding="utf-8")
        self.log("guardado", id=doc_id, asignatura=subject_id, tipo=kind, tema=topic, version=version)
        return record

    def update_meta(self, doc_id: str, **changes) -> dict:
        with _lock:
            idx = self._read_index()
            rec = idx["documents"][doc_id]
            rec.update(changes)
            rec["updated"] = now()
            self._write_index(idx)
            md_path = self.root / rec["path"]
            md_path.with_suffix(".meta.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            return rec

    # ---------- consultar ----------
    def list_documents(self, subject_id: str | None = None) -> list[dict]:
        docs = list(self._read_index()["documents"].values())
        if subject_id:
            docs = [d for d in docs if d["subject"] == subject_id]
        return sorted(docs, key=lambda d: d["updated"], reverse=True)

    def get(self, doc_id: str) -> tuple[dict, str]:
        rec = self._read_index()["documents"].get(doc_id)
        if not rec:
            raise KeyError(doc_id)
        return rec, (self.root / rec["path"]).read_text(encoding="utf-8")

    def source_text(self, rec: dict) -> str:
        p = self.root / rec["path"]
        txt = p.with_suffix(".source.txt")
        return txt.read_text(encoding="utf-8") if txt.exists() else ""

    def save_source_text(self, rec: dict, text: str) -> None:
        (self.root / rec["path"]).with_suffix(".source.txt").write_text(text, encoding="utf-8")

    def export_path(self, rec: dict, ext: str) -> Path:
        return (self.root / rec["path"]).with_suffix(ext)

    def verify(self, doc_id: str) -> dict:
        rec, md = self.get(doc_id)
        md_path = self.root / rec["path"]
        result = {
            "markdown_existe": md_path.exists(),
            "markdown_intacto": sha256_bytes(md.encode("utf-8")) == rec.get("md_hash"),
            "metadatos_existen": md_path.with_suffix(".meta.json").exists(),
            "pdf_existe": md_path.with_suffix(".pdf").exists(),
            "original_existe": bool(rec.get("source_path")) and (self.root / rec["source_path"]).exists(),
            "carpeta": str(md_path.parent),
        }
        result["correcto"] = all(v for k, v in result.items() if k not in ("carpeta", "pdf_existe"))
        return result

    # ---------- mover (corregir la asignatura) ----------
    def move(self, doc_id: str, new_subject: str) -> dict:
        with _lock:
            idx = self._read_index()
            rec = idx["documents"][doc_id]
            old_md = self.root / rec["path"]
            new_folder = self.subject_dir(new_subject) / self.subfolders[rec["kind"]]
            new_md = new_folder / old_md.name
            if new_md.exists():
                new_md = new_folder / f"{old_md.stem} ({doc_id[:4]}).md"
            for ext in (".md", ".meta.json", ".pdf", ".html", ".source.txt"):
                src = old_md.with_suffix(ext)
                if src.exists():
                    shutil.move(str(src), str(new_md.with_suffix(ext)))
            old_v, new_v = old_md.parent / ".versiones", new_md.parent / ".versiones"
            if old_v.exists():
                new_v.mkdir(exist_ok=True)
                for f in old_v.glob(f"{old_md.stem}.v*.md"):
                    shutil.move(str(f), str(new_v / f.name.replace(old_md.stem, new_md.stem, 1)))
            old_subject = rec["subject"]
            rec.update(subject=new_subject, path=str(new_md.relative_to(self.root)), updated=now(),
                       classification_corrected=True)
            self._write_index(idx)
            new_md.with_suffix(".meta.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        self.log("reclasificado", id=doc_id, de=old_subject, a=new_subject)
        return rec

    # ---------- borrar ----------
    def delete(self, doc_id: str) -> None:
        with _lock:
            idx = self._read_index()
            rec = idx["documents"].pop(doc_id)
            md = self.root / rec["path"]
            for ext in (".md", ".meta.json", ".pdf", ".html", ".source.txt"):
                p = md.with_suffix(ext)
                if p.exists():
                    p.unlink()
            vdir = md.parent / ".versiones"
            for f in vdir.glob(f"{md.stem}.v*.md") if vdir.exists() else []:
                f.unlink()
            self._write_index(idx)
        self.log("borrado", id=doc_id, tema=rec.get("topic"))

    # ---------- correcciones ----------
    def add_correction(self, subject_id: str, text: str, apply_future: bool, doc_id: str | None) -> dict:
        item = {"id": uuid.uuid4().hex[:8], "fecha": now(), "asignatura": subject_id, "texto": text,
                "aplicar_en_futuro": apply_future, "documento": doc_id}
        with _lock, open(self.corrections_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
        return item

    def corrections(self, subject_id: str | None = None, only_active: bool = False) -> list[dict]:
        if not self.corrections_path.exists():
            return []
        items = [json.loads(l) for l in self.corrections_path.read_text(encoding="utf-8").splitlines() if l.strip()]
        if subject_id:
            items = [i for i in items if i["asignatura"] == subject_id]
        if only_active:
            items = [i for i in items if i["aplicar_en_futuro"]]
        return items
