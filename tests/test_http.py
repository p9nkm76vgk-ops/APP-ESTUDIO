"""Prueba de extremo a extremo de la API web: arranca el servidor real en un puerto libre."""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).parent))
from helpers import CATALAN_TXT, make_pdf  # noqa: E402


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class TestHttp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        port = free_port()
        cls.base = f"http://127.0.0.1:{port}"
        env = {**os.environ, "ESTUDIO_DATA_DIR": str(cls.tmp / "datos"), "ESTUDIO_PORT": str(port),
               "ESTUDIO_ANTHROPIC_API_KEY": ""}
        cls.proc = subprocess.Popen([sys.executable, "-m", "app.main"], cwd=ROOT, env=env,
                                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        for _ in range(60):
            try:
                requests.get(cls.base + "/api/status", timeout=1)
                break
            except requests.RequestException:
                time.sleep(0.25)

    @classmethod
    def tearDownClass(cls):
        cls.proc.terminate()
        cls.proc.wait(timeout=10)

    def _wait(self, job_id):
        for _ in range(200):
            job = requests.get(f"{self.base}/api/jobs/{job_id}").json()
            if job["status"] != "en_curso":
                return job
            time.sleep(0.1)
        self.fail("El trabajo no terminó")

    def test_end_to_end(self):
        self.assertEqual(requests.get(self.base + "/").status_code, 200)
        subjects = requests.get(self.base + "/api/subjects").json()
        self.assertEqual(len(subjects["subjects"]), 9)

        pdf = make_pdf(self.tmp / "sonet.pdf", CATALAN_TXT)
        r = requests.post(self.base + "/api/process", files={"file": ("sonet.pdf", pdf.read_bytes())},
                          data={"kind": "apuntes", "subject": ""})
        self.assertEqual(r.status_code, 200, r.text)
        job = self._wait(r.json()["id"])
        self.assertEqual(job["status"], "completado", job)
        self.assertEqual(job["classification"]["asignatura"], "catalan")
        doc_id = job["document_id"]

        doc = requests.get(f"{self.base}/api/documents/{doc_id}").json()
        self.assertIn("Preguntas de recuperación", doc["sections"])
        self.assertTrue(doc["goodnotes"]["nombre"].endswith(".pdf"))

        pdf_r = requests.get(f"{self.base}/api/documents/{doc_id}/file.pdf")
        self.assertEqual(pdf_r.headers["content-type"], "application/pdf")
        self.assertTrue(pdf_r.content.startswith(b"%PDF"))
        self.assertIn("text/html", requests.get(f"{self.base}/api/documents/{doc_id}/file.html").headers["content-type"])

        edited = requests.put(f"{self.base}/api/documents/{doc_id}", json={"markdown": doc["markdown"] + "\n\nNota."}).json()
        self.assertEqual(edited["meta"]["version"], 2)
        self.assertTrue(requests.post(f"{self.base}/api/documents/{doc_id}/verify").json()["correcto"])
        self.assertEqual(requests.post(f"{self.base}/api/documents/{doc_id}/approve").json()["meta"]["status"], "definitivo")

        dup = self._wait(requests.post(self.base + "/api/process", files={"file": ("sonet.pdf", pdf.read_bytes())},
                                       data={"kind": "apuntes"}).json()["id"])
        self.assertEqual(dup["status"], "duplicado")

        regen = requests.post(f"{self.base}/api/documents/{doc_id}/regenerate", json={"heading": "Preguntas de recuperación"})
        self.assertEqual(regen.status_code, 400)
        self.assertIn("IA", regen.json()["error"])

        hist = requests.get(self.base + "/api/history").json()["history"]
        self.assertTrue(any(h["evento"] == "duplicado_detectado" for h in hist))

        self.assertEqual(requests.delete(f"{self.base}/api/documents/{doc_id}").status_code, 200)
        self.assertEqual(requests.get(f"{self.base}/api/documents/{doc_id}").status_code, 404)

    def test_errors_are_readable(self):
        r = requests.post(self.base + "/api/process", data={"kind": "apuntes"})
        self.assertEqual(r.status_code, 400)
        self.assertIn("archivo", r.json()["error"])
        bad = self._wait(requests.post(self.base + "/api/process", files={"file": ("a.xyz", b"hola")}).json()["id"])
        self.assertEqual(bad["status"], "error")
        self.assertIn("no está soportado", bad["message"])


if __name__ == "__main__":
    unittest.main()
