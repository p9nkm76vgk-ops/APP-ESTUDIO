"""Servidor web (Starlette + uvicorn). Ejecuta:  python -m app.main"""
from __future__ import annotations

import os
from pathlib import Path

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, PlainTextResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .config import ROOT
from . import goodnotes


def load_dotenv(path: Path = ROOT / ".env") -> None:
    """Lee .env (KEY=valor) sin dependencias. No sobrescribe variables ya definidas."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


load_dotenv()
from .pipeline import Engine  # noqa: E402  (después de leer .env)

engine = Engine()
MAX_UPLOAD = 40 * 1024 * 1024


def err(msg: str, code: int = 400) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=code)


async def index(request: Request):
    return FileResponse(ROOT / "static" / "index.html")


async def status(request: Request):
    return JSONResponse(engine.status())


async def subjects(request: Request):
    docs = engine.storage.list_documents()
    out = []
    for s in engine.subjects.values():
        out.append({"id": s.id, "name": s.name, "folder": s.folder, "language": s.language,
                    "primary": s.design["primary"], "soft": s.design["soft"],
                    "count": sum(1 for d in docs if d["subject"] == s.id)})
    return JSONResponse({"subjects": out, "output_types": engine.cfg["output_types"]})


async def process(request: Request):
    form = await request.form()
    upload = form.get("file")
    if upload is None or not getattr(upload, "filename", ""):
        return err("No se ha recibido ningún archivo.")
    data = await upload.read()
    if len(data) > MAX_UPLOAD:
        return err("El archivo supera los 40 MB.")
    if not data:
        return err("El archivo está vacío.")
    subject = form.get("subject") or None
    if subject and subject not in engine.subjects:
        return err("Asignatura desconocida.")
    job = engine.submit(upload.filename, data, kind=form.get("kind") or "apuntes", subject_id=subject,
                        force=form.get("force") == "1", extra=(form.get("extra") or "")[:1000])
    return JSONResponse(job.to_dict())


async def job_status(request: Request):
    job = engine.jobs.get(request.path_params["job_id"])
    return JSONResponse(job.to_dict()) if job else err("Trabajo no encontrado.", 404)


async def job_confirm(request: Request):
    body = await request.json()
    if body.get("subject") not in engine.subjects:
        return err("Elige una asignatura válida.")
    try:
        job = engine.confirm(request.path_params["job_id"], body["subject"], body.get("topic") or None)
    except KeyError as e:
        return err(str(e), 404)
    return JSONResponse(job.to_dict())


async def documents(request: Request):
    return JSONResponse({"documents": engine.storage.list_documents(request.query_params.get("subject"))})


def _doc_or_404(doc_id: str):
    try:
        return engine.storage.get(doc_id)
    except KeyError:
        return None


async def document(request: Request):
    doc_id = request.path_params["doc_id"]
    found = _doc_or_404(doc_id)
    if not found:
        return err("Documento no encontrado.", 404)
    rec, md = found
    from .generate import list_sections
    subject = engine.subjects[rec["subject"]]
    return JSONResponse({"meta": rec, "markdown": md, "sections": list_sections(md),
                         "goodnotes": {"nombre": goodnotes.filename_for(subject, rec["topic"], rec.get("kind_label", rec["kind"]), rec["version"]),
                                       "pasos": goodnotes.import_instructions(subject)}})


async def document_update(request: Request):
    doc_id = request.path_params["doc_id"]
    if not _doc_or_404(doc_id):
        return err("Documento no encontrado.", 404)
    body = await request.json()
    md = (body.get("markdown") or "").strip()
    if not md:
        return err("El documento no puede quedar vacío.")
    return JSONResponse({"meta": engine.save_edit(doc_id, md)})


async def document_delete(request: Request):
    doc_id = request.path_params["doc_id"]
    if not _doc_or_404(doc_id):
        return err("Documento no encontrado.", 404)
    engine.storage.delete(doc_id)
    return JSONResponse({"ok": True})


async def document_action(request: Request):
    doc_id, action = request.path_params["doc_id"], request.path_params["action"]
    if not _doc_or_404(doc_id):
        return err("Documento no encontrado.", 404)
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}
    try:
        if action == "regenerate":
            return JSONResponse({"meta": engine.regenerate(doc_id, body.get("heading", ""), body.get("instruction", ""))})
        if action == "reclassify":
            if body.get("subject") not in engine.subjects:
                return err("Asignatura desconocida.")
            return JSONResponse({"meta": engine.reclassify(doc_id, body["subject"])})
        if action == "approve":
            return JSONResponse({"meta": engine.approve(doc_id)})
        if action == "verify":
            return JSONResponse(engine.storage.verify(doc_id))
        if action == "correction":
            rec, _ = engine.storage.get(doc_id)
            text = (body.get("text") or "").strip()
            if not text:
                return err("Escribe la corrección.")
            return JSONResponse(engine.storage.add_correction(rec["subject"], text, bool(body.get("apply_future")), doc_id))
    except ValueError as e:
        return err(str(e))
    except Exception as e:
        return err(f"No se ha podido completar la operación: {e}", 500)
    return err("Acción desconocida.", 404)


async def document_file(request: Request):
    doc_id, fmt = request.path_params["doc_id"], request.path_params["fmt"]
    found = _doc_or_404(doc_id)
    if not found:
        return err("Documento no encontrado.", 404)
    rec, md = found
    subject = engine.subjects[rec["subject"]]
    if fmt == "md":
        return PlainTextResponse(md, media_type="text/markdown; charset=utf-8")
    path = engine.storage.export_path(rec, f".{fmt}")
    if fmt not in ("pdf", "html"):
        return err("Formato no soportado.")
    if not path.exists():
        engine.export(doc_id)
    if fmt == "html":
        return Response(path.read_text(encoding="utf-8"), media_type="text/html; charset=utf-8")
    name = goodnotes.filename_for(subject, rec["topic"], rec.get("kind_label", rec["kind"]), rec["version"])
    disposition = "inline" if request.query_params.get("inline") else "attachment"
    return FileResponse(path, media_type="application/pdf", filename=name, content_disposition_type=disposition)


async def history(request: Request):
    return JSONResponse({"history": engine.storage.history()})


async def corrections(request: Request):
    return JSONResponse({"corrections": engine.storage.corrections(request.query_params.get("subject"))})


routes = [
    Route("/", index),
    Route("/api/status", status),
    Route("/api/subjects", subjects),
    Route("/api/process", process, methods=["POST"]),
    Route("/api/jobs/{job_id}", job_status),
    Route("/api/jobs/{job_id}/confirm", job_confirm, methods=["POST"]),
    Route("/api/documents", documents),
    Route("/api/documents/{doc_id}", document),
    Route("/api/documents/{doc_id}", document_update, methods=["PUT"]),
    Route("/api/documents/{doc_id}", document_delete, methods=["DELETE"]),
    Route("/api/documents/{doc_id}/file.{fmt}", document_file),
    Route("/api/documents/{doc_id}/{action}", document_action, methods=["POST"]),
    Route("/api/history", history),
    Route("/api/corrections", corrections),
    Mount("/static", StaticFiles(directory=ROOT / "static"), name="static"),
]

app = Starlette(routes=routes)


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("ESTUDIO_HOST", "127.0.0.1")   # solo tu equipo por defecto
    port = int(os.environ.get("ESTUDIO_PORT", "8765"))
    print(f"Sistema de Estudio en http://{host}:{port}  (proveedor: {engine.provider.name})")
    uvicorn.run(app, host=host, port=port, log_level="warning")
