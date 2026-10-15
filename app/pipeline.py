"""Flujo completo: recibir → extraer → clasificar → generar → controlar calidad → exportar → guardar → registrar."""
from __future__ import annotations

import tempfile
import threading
import traceback
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import export, goodnotes, quality
from .classify import classify, detect_language
from .config import load_app_config, load_subjects
from .extract import ExtractionError, extract
from .generate import generate, regenerate_section
from .providers import ProviderError, get_provider
from .storage import Storage, sha256_bytes

STEPS = ["recibido", "extrayendo", "clasificando", "generando", "calidad", "exportando", "guardado"]


@dataclass
class Job:
    id: str
    filename: str
    step: str = "recibido"
    status: str = "en_curso"   # en_curso | necesita_confirmacion | completado | error | duplicado
    message: str = ""
    classification: dict = field(default_factory=dict)
    document_id: str | None = None
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = self.__dict__.copy()
        d["progress"] = round(100 * (STEPS.index(self.step) + (1 if self.status == "completado" else 0)) / len(STEPS))
        return d


class Engine:
    def __init__(self, data_dir: Path | None = None, provider_name: str | None = None):
        self.cfg = load_app_config()
        if data_dir:
            self.cfg["data_dir"] = Path(data_dir)
        self.subjects = load_subjects()
        self.storage = Storage(self.cfg["data_dir"], self.subjects, self.cfg["subfolders"])
        self.provider = get_provider(provider_name or self.cfg.get("provider", "auto"), self.cfg.get("model"))
        self.jobs: dict[str, Job] = {}
        self._pending: dict[str, dict] = {}

    # ------------------------------------------------------------------ helpers
    def kind_label(self, kind: str) -> str:
        return self.cfg["output_types"].get(kind, kind)

    def status(self) -> dict:
        return {
            "proveedor": self.provider.name,
            "usa_ia": self.provider.uses_ai,
            "modelo": self.cfg.get("model") if self.provider.uses_ai else None,
            "carpeta_datos": str(self.storage.root),
            "goodnotes": goodnotes.CAPABILITIES,
        }

    # ------------------------------------------------------------------ procesar
    def submit(self, filename: str, data: bytes, kind: str = "apuntes", subject_id: str | None = None,
               force: bool = False, extra: str = "", background: bool = True) -> Job:
        job = Job(id=uuid.uuid4().hex[:10], filename=filename)
        self.jobs[job.id] = job
        args = (job, filename, data, kind, subject_id, force, extra)
        if background:
            threading.Thread(target=self._run, args=args, daemon=True).start()
        else:
            self._run(*args)
        return job

    def _run(self, job: Job, filename: str, data: bytes, kind: str, subject_id: str | None, force: bool, extra: str):
        try:
            if kind not in self.cfg["output_types"]:
                raise ValueError(f"Tipo de material desconocido: {kind}")
            source_hash = sha256_bytes(data)
            dup = self.storage.find_duplicate(source_hash, kind)
            if dup and not force:
                job.status, job.document_id = "duplicado", dup["id"]
                job.message = (f"Este archivo ya se procesó como «{self.kind_label(kind)}» "
                               f"({self.subjects[dup['subject']].name}, v{dup['version']}). "
                               "Ábrelo o vuelve a generarlo si quieres una versión nueva.")
                self.storage.log("duplicado_detectado", archivo=filename, id=dup["id"])
                return

            job.step = "extrayendo"
            with tempfile.TemporaryDirectory() as tmp:
                p = Path(tmp) / Path(filename).name
                p.write_bytes(data)
                ex = extract(p)
            job.warnings += ex.warnings
            if ex.char_count < 50:
                raise ExtractionError("No hay texto suficiente en el documento para generar apuntes sin inventar contenido.")

            job.step = "clasificando"
            cls = classify(ex.text, self.subjects, filename, self.cfg["classification_min_confidence"])
            job.classification = {
                "asignatura": cls.subject_id, "confianza": cls.confidence, "idioma": cls.language,
                "tema": cls.topic, "mezcla": cls.mixed_with, "motivo": cls.reason,
                "puntuaciones": dict(sorted(cls.scores.items(), key=lambda kv: -kv[1])[:4]),
            }
            if subject_id is None:
                if cls.needs_review or cls.subject_id is None:
                    job.status, job.message = "necesita_confirmacion", cls.reason
                    self._pending[job.id] = {"filename": filename, "data": data, "kind": kind, "extra": extra,
                                             "text": ex.text, "topic": cls.topic, "hash": source_hash}
                    return
                subject_id = cls.subject_id
            self._generate_and_save(job, filename, data, ex.text, cls.topic, subject_id, kind, source_hash, extra,
                                    corrected=subject_id != cls.subject_id)
        except (ExtractionError, ProviderError, ValueError) as e:
            job.status, job.message = "error", str(e)
            self.storage.log("error", archivo=filename, paso=job.step, detalle=str(e))
        except Exception as e:  # error inesperado: se registra con detalle
            job.status, job.message = "error", f"Error inesperado en el paso «{job.step}»: {e}"
            self.storage.log("error", archivo=filename, paso=job.step, detalle=traceback.format_exc()[-1500:])

    def confirm(self, job_id: str, subject_id: str, topic: str | None = None) -> Job:
        job = self.jobs[job_id]
        p = self._pending.pop(job_id, None)
        if p is None:
            raise KeyError("No hay nada pendiente de confirmar para este trabajo.")
        job.status = "en_curso"

        def run():
            try:
                self._generate_and_save(job, p["filename"], p["data"], p["text"], topic or p["topic"], subject_id,
                                        p["kind"], p["hash"], p["extra"], corrected=True)
            except Exception as e:
                job.status, job.message = "error", str(e)
                self.storage.log("error", archivo=p["filename"], paso=job.step, detalle=str(e))
        threading.Thread(target=run, daemon=True).start()
        return job

    def _generate_and_save(self, job: Job, filename: str, data: bytes, text: str, topic: str, subject_id: str,
                           kind: str, source_hash: str, extra: str, corrected: bool):
        subject = self.subjects[subject_id]
        corrections = [c["texto"] for c in self.storage.corrections(subject_id, only_active=True)]

        job.step = "generando"
        md, warns = generate(self.provider, subject, text, topic, kind, corrections, extra, self.cfg.get("max_tokens", 8000))
        job.warnings += warns

        job.step = "calidad"
        checks = quality.run_checks(md, text, subject.language, detect_language(md), self.provider.uses_ai)

        original = self.storage.save_original(subject_id, filename, data, source_hash)
        meta = {
            "source_filename": filename, "source_hash": source_hash,
            "source_path": str(original.relative_to(self.storage.root)),
            "provider": self.provider.name, "model": self.cfg.get("model") if self.provider.uses_ai else None,
            "quality": checks, "quality_summary": quality.summary(checks),
            "classification": job.classification, "classification_corrected": corrected,
            "kind_label": self.kind_label(kind), "warnings": job.warnings,
        }
        rec = self.storage.save_document(subject_id=subject_id, kind=kind, topic=topic, markdown=md, meta=meta)
        self.storage.save_source_text(rec, text)

        job.step = "exportando"
        self.export(rec["id"])

        job.step, job.status, job.document_id = "guardado", "completado", rec["id"]
        job.message = f"Guardado en {subject.name} / {self.cfg['subfolders'][kind]}."

    # ------------------------------------------------------------------ documentos
    def export(self, doc_id: str) -> dict:
        rec, md = self.storage.get(doc_id)
        subject = self.subjects[rec["subject"]]
        meta = {**rec, "kind_label": rec.get("kind_label") or self.kind_label(rec["kind"])}
        pdf = export.markdown_to_pdf(md, self.storage.export_path(rec, ".pdf"), subject, meta)
        self.storage.export_path(rec, ".html").write_text(export.markdown_to_html(md, subject, meta), encoding="utf-8")
        return {"pdf": str(pdf), "goodnotes_nombre": goodnotes.filename_for(subject, rec["topic"], meta["kind_label"], rec["version"])}

    def save_edit(self, doc_id: str, markdown: str, note: str = "edición manual") -> dict:
        rec, _ = self.storage.get(doc_id)
        source = self.storage.source_text(rec)
        subject = self.subjects[rec["subject"]]
        checks = quality.run_checks(markdown, source, subject.language, detect_language(markdown), True)
        rec = self.storage.save_document(subject_id=rec["subject"], kind=rec["kind"], topic=rec["topic"], markdown=markdown,
                                         meta={"quality": checks, "quality_summary": quality.summary(checks),
                                               "last_change": note, "status": "borrador"}, doc_id=doc_id)
        self.export(doc_id)
        return rec

    def regenerate(self, doc_id: str, heading: str, instruction: str = "") -> dict:
        rec, md = self.storage.get(doc_id)
        subject = self.subjects[rec["subject"]]
        corrections = [c["texto"] for c in self.storage.corrections(rec["subject"], only_active=True)]
        new_md = regenerate_section(self.provider, subject, md, heading, self.storage.source_text(rec), instruction, corrections)
        return self.save_edit(doc_id, new_md, note=f"sección regenerada: {heading}")

    def reclassify(self, doc_id: str, subject_id: str) -> dict:
        rec = self.storage.move(doc_id, subject_id)
        self.export(doc_id)
        return rec

    def approve(self, doc_id: str) -> dict:
        rec = self.storage.update_meta(doc_id, status="definitivo")
        self.storage.log("aprobado", id=doc_id)
        return rec
