"""Pruebas del motor: extracción, clasificación, generación, calidad, almacenamiento y exportación.

Ejecutar:  python -m unittest discover -s tests -v
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).parent))

from helpers import AMBIGUO_TXT, CATALAN_TXT, FISICA_TXT, LENGUA_TXT, make_docx, make_image, make_pdf, make_pptx  # noqa: E402

from app import quality  # noqa: E402
from app.classify import classify, detect_language, detect_topic  # noqa: E402
from app.config import load_subjects  # noqa: E402
from app.export import markdown_to_pdf, parse_blocks  # noqa: E402
from app.extract import ExtractionError, extract  # noqa: E402
from app.generate import build_system_prompt, get_section, list_sections  # noqa: E402
from app.pipeline import Engine  # noqa: E402
from app.providers import OfflineProvider, ProviderError  # noqa: E402
from app.providers.anthropic_api import AnthropicProvider  # noqa: E402

SUBJECTS = load_subjects()


class TestConfig(unittest.TestCase):
    def test_nine_subjects_with_full_config(self):
        self.assertEqual(len(SUBJECTS), 9)
        for s in SUBJECTS.values():
            for key in ("primary", "accent", "soft", "background", "text"):
                self.assertIn(key, s.design, s.id)
            self.assertTrue(s.structure and s.exercise_types and s.quality and s.keywords, s.id)


class TestExtract(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_txt_docx_pdf_pptx(self):
        txt = self.tmp / "a.txt"
        txt.write_text(LENGUA_TXT, encoding="utf-8")
        for path in (txt, make_docx(self.tmp / "a.docx", LENGUA_TXT), make_pdf(self.tmp / "a.pdf", LENGUA_TXT),
                     make_pptx(self.tmp / "a.pptx", LENGUA_TXT)):
            ex = extract(path)
            self.assertIn("pasiva refleja", ex.text.lower(), path.suffix)

    def test_image_ocr(self):
        img = make_image(self.tmp / "foto.png", "The present perfect tense\nWe use it for past actions\nwith a result in the present")
        ex = extract(img)
        self.assertTrue(ex.used_ocr)
        self.assertIn("present perfect", ex.text.lower())

    def test_unsupported_format_message(self):
        p = self.tmp / "x.xyz"
        p.write_text("hola")
        with self.assertRaises(ExtractionError) as ctx:
            extract(p)
        self.assertIn("no está soportado", str(ctx.exception))

    def test_short_text_warns(self):
        p = self.tmp / "corto.txt"
        p.write_text("Muy poco texto.")
        self.assertTrue(extract(p).warnings)


class TestClassify(unittest.TestCase):
    def test_language(self):
        self.assertEqual(detect_language(LENGUA_TXT), "es")
        self.assertEqual(detect_language(CATALAN_TXT), "ca")
        self.assertEqual(detect_language("The cat is on the table and it was happy with the food"), "en")

    def test_subjects(self):
        self.assertEqual(classify(LENGUA_TXT, SUBJECTS).subject_id, "lengua")
        self.assertEqual(classify(CATALAN_TXT, SUBJECTS).subject_id, "catalan")
        self.assertEqual(classify(FISICA_TXT, SUBJECTS).subject_id, "fisica")

    def test_ambiguous_needs_review(self):
        c = classify(AMBIGUO_TXT, SUBJECTS)
        self.assertTrue(c.needs_review)

    def test_mixed_subjects_detected(self):
        c = classify(LENGUA_TXT + "\n" + FISICA_TXT * 3, SUBJECTS)
        self.assertTrue(c.needs_review)

    def test_topic(self):
        self.assertEqual(detect_topic("POEMA RETRATO DE MACHADO\ntexto"), "Poema Retrato de Machado")
        self.assertEqual(detect_topic("LOS VALORES DEL SE.\n"), "Los Valores del SE")


class TestGenerateAndOffline(unittest.TestCase):
    def test_system_prompt_uses_subject_config_and_corrections(self):
        p = build_system_prompt(SUBJECTS["catalan"], "apuntes", ["Figures sempre amb exemple"])
        self.assertIn("Catalán", p)
        self.assertIn("catalán", p)  # idioma
        self.assertIn("Figures sempre amb exemple", p)
        self.assertIn("Preguntas de recuperación", p)

    def test_offline_keeps_sections_and_adds_retrieval(self):
        user = f"<titulo>SE</titulo>\n<tipo>apuntes</tipo>\n<documento>\n{LENGUA_TXT}\n</documento>"
        md = OfflineProvider().generate("", user)
        secs = list_sections(md)
        self.assertIn("2. SE reflexivo", secs)
        self.assertIn("Preguntas de recuperación", secs)
        self.assertIsNotNone(get_section(md, "Preguntas de recuperación"))


class TestQuality(unittest.TestCase):
    def test_detects_invented_data(self):
        output = "# SE\n\n## Pasiva refleja\n\n- Lo explicó Bello en 1847 en Caracas.\n\n## Preguntas de recuperación\n\n1. ¿Qué es?"
        checks = {c["id"]: c for c in quality.run_checks(output, LENGUA_TXT, "es", "es", True)}
        self.assertEqual(checks["fidelidad"]["status"], "aviso")
        for term in ("1847", "Bello", "Caracas"):
            self.assertIn(term, checks["fidelidad"]["detail"])

    def test_faithful_output_ok_and_never_claims_unverifiable(self):
        output = ("# SE\n\n## Se variante de le\n\n- Se lo conté a tu hermano.\n\n## Se reflexivo\n\n- El niño se lava.\n\n"
                  "## Pasiva refleja\n\n- Se descubrió el engaño en 1898.\n\n## Preguntas de recuperación\n\n1. ¿Qué es?")
        checks = {c["id"]: c for c in quality.run_checks(output, LENGUA_TXT, "es", "es", True)}
        self.assertEqual(checks["fidelidad"]["status"], "ok")
        self.assertEqual(checks["cobertura"]["status"], "ok")
        self.assertEqual(checks["formulas"]["status"], "no_verificable")
        self.assertEqual(checks["pedagogia"]["status"], "no_verificable")

    def test_missing_retrieval_and_wrong_language(self):
        checks = {c["id"]: c for c in quality.run_checks("# X\n\n## Uno\n\ntexto", LENGUA_TXT, "ca", "es", True)}
        self.assertEqual(checks["recuperacion"]["status"], "aviso")
        self.assertEqual(checks["idioma"]["status"], "aviso")


class TestExport(unittest.TestCase):
    def test_blocks(self):
        b = parse_blocks("# T\n\n## S\n\n| a | b |\n| --- | --- |\n| 1 | 2 |\n\n> cita\n\n- uno\n    - dos\n\n1. tres")
        kinds = [x[0] for x in b]
        self.assertEqual(kinds, ["h", "h", "table", "quote", "list", "list"])
        self.assertEqual(b[2][1], [["a", "b"], ["1", "2"]])

    def test_pdf_is_valid_for_every_subject(self):
        from pypdf import PdfReader
        tmp = Path(tempfile.mkdtemp())
        md = "# Título → prueba\n\n## Sección\n\n**negrita** y *cursiva* · «comillas» l·l ç\n\n| Columna larguísima | b |\n| --- | --- |\n| Estrofa | 2 |\n\n> Así lo escribiría"
        for s in SUBJECTS.values():
            out = markdown_to_pdf(md, tmp / f"{s.id}.pdf", s, {"topic": "Prueba", "kind_label": "Apuntes", "version": 1})
            text = PdfReader(str(out)).pages[0].extract_text()
            self.assertIn("Sección", text, s.id)


class TestAnthropicProvider(unittest.TestCase):
    """Sin red: se simula la respuesta de la API."""

    def _resp(self, status, payload):
        r = mock.Mock(status_code=status, text=json.dumps(payload))
        r.json.return_value = payload
        return r

    def test_payload_and_text(self):
        p = AnthropicProvider(api_key="test-key", model="claude-sonnet-5-5")
        ok = self._resp(200, {"content": [{"type": "text", "text": "# Apuntes"}], "stop_reason": "end_turn"})
        with mock.patch("app.providers.anthropic_api.requests.post", return_value=ok) as post:
            self.assertEqual(p.generate("sys", "user", 100), "# Apuntes")
        kwargs = post.call_args.kwargs
        self.assertEqual(kwargs["json"]["model"], "claude-sonnet-5-5")
        self.assertEqual(kwargs["json"]["system"], "sys")
        self.assertEqual(kwargs["headers"]["x-api-key"], "test-key")

    def test_invalid_key_message(self):
        p = AnthropicProvider(api_key="bad", model="m")
        with mock.patch("app.providers.anthropic_api.requests.post", return_value=self._resp(401, {})):
            with self.assertRaises(ProviderError) as ctx:
                p.generate("s", "u")
        self.assertIn("401", str(ctx.exception))

    def test_retries_when_overloaded(self):
        p = AnthropicProvider(api_key="k", model="m")
        seq = [self._resp(529, {}), self._resp(200, {"content": [{"type": "text", "text": "ok"}]})]
        with mock.patch("app.providers.anthropic_api.requests.post", side_effect=seq), \
             mock.patch("app.providers.anthropic_api.time.sleep"):
            self.assertEqual(p.generate("s", "u"), "ok")

    def test_key_only_from_app_variable(self):
        from app.providers import get_provider
        with mock.patch.dict("os.environ", {"ESTUDIO_ANTHROPIC_API_KEY": ""}, clear=False):
            self.assertEqual(get_provider("auto").name, "offline")
            with self.assertRaises(ProviderError):
                get_provider("anthropic")


class TestPipelineAndStorage(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.engine = Engine(data_dir=self.tmp / "datos", provider_name="offline")
        self.docx = make_docx(self.tmp / "valores.docx", LENGUA_TXT)

    def _run(self, path, **kw):
        return self.engine.submit(path.name, path.read_bytes(), background=False, **kw)

    def test_full_flow_tree_metadata_pdf(self):
        job = self._run(self.docx)
        self.assertEqual(job.status, "completado", job.message)
        rec, md = self.engine.storage.get(job.document_id)
        self.assertEqual(rec["subject"], "lengua")
        self.assertTrue(rec["path"].startswith("01-Lengua-Castellana/Apuntes/"))
        for key in ("subject", "topic", "created", "source_filename", "source_hash", "version", "quality"):
            self.assertIn(key, rec)
        v = self.engine.storage.verify(job.document_id)
        self.assertTrue(v["correcto"] and v["pdf_existe"], v)
        self.assertTrue((self.tmp / "datos" / "09-Business" / "Preguntas-de-Examen").is_dir())

    def test_duplicates(self):
        first = self._run(self.docx)
        second = self._run(self.docx)
        self.assertEqual(second.status, "duplicado")
        self.assertEqual(second.document_id, first.document_id)
        other_kind = self._run(self.docx, kind="tarjetas")
        self.assertEqual(other_kind.status, "completado")
        forced = self._run(self.docx, force=True)
        self.assertEqual(forced.status, "completado")
        originals = list((self.tmp / "datos" / "01-Lengua-Castellana" / "Apuntes-Originales").iterdir())
        self.assertEqual(len(originals), 1)  # el original no se duplica

    def test_versions_on_edit(self):
        job = self._run(self.docx)
        rec, md = self.engine.storage.get(job.document_id)
        rec2 = self.engine.save_edit(job.document_id, md + "\n\nNota añadida a mano.")
        self.assertEqual(rec2["version"], 2)
        vfile = (self.tmp / "datos" / rec2["path"]).parent / ".versiones"
        self.assertEqual(len(list(vfile.glob("*.v1.md"))), 1)

    def test_ambiguous_waits_for_confirmation_then_saves(self):
        p = self.tmp / "notas.txt"
        p.write_text(AMBIGUO_TXT, encoding="utf-8")
        job = self._run(p)
        self.assertEqual(job.status, "necesita_confirmacion")
        self.assertEqual(self.engine.storage.list_documents(), [])  # no guarda sin preguntar
        self.engine.confirm(job.id, "ingles", "Notas")
        import time
        for _ in range(100):
            if job.status != "en_curso":
                break
            time.sleep(0.05)
        self.assertEqual(job.status, "completado", job.message)
        self.assertEqual(self.engine.storage.get(job.document_id)[0]["subject"], "ingles")

    def test_reclassify_moves_files(self):
        job = self._run(self.docx)
        rec = self.engine.reclassify(job.document_id, "catalan")
        self.assertTrue(rec["path"].startswith("02-Catalan/"))
        self.assertTrue(self.engine.storage.verify(job.document_id)["correcto"])

    def test_manual_subject_and_corrections_reach_prompt(self):
        self.engine.storage.add_correction("fisica", "Unidades siempre en SI", True, None)
        self.engine.storage.add_correction("fisica", "Solo para este documento", False, None)
        active = [c["texto"] for c in self.engine.storage.corrections("fisica", only_active=True)]
        self.assertEqual(active, ["Unidades siempre en SI"])

    def test_delete(self):
        job = self._run(self.docx)
        rec, _ = self.engine.storage.get(job.document_id)
        self.engine.storage.delete(job.document_id)
        self.assertFalse((self.tmp / "datos" / rec["path"]).exists())
        with self.assertRaises(KeyError):
            self.engine.storage.get(job.document_id)

    def test_unreadable_file_reports_error(self):
        p = self.tmp / "roto.pdf"
        p.write_bytes(b"esto no es un pdf")
        job = self._run(p)
        self.assertEqual(job.status, "error")
        self.assertIn("No se ha podido leer", job.message)

    def test_regenerate_section_requires_ai(self):
        job = self._run(self.docx)
        with self.assertRaises(ValueError):
            self.engine.regenerate(job.document_id, "Preguntas de recuperación")


if __name__ == "__main__":
    unittest.main()
