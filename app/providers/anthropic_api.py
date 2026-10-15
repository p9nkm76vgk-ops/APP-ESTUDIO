"""Proveedor Claude mediante la API de Anthropic (Messages API).

Usa `requests` en lugar del SDK para no añadir dependencias. La clave se lee de la
variable de entorno ESTUDIO_ANTHROPIC_API_KEY (nunca del código ni del navegador).
Datos enviados: el texto extraído del documento y las instrucciones de la asignatura.
"""
from __future__ import annotations

import time

import requests

from .base import Provider, ProviderError

API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"


class AnthropicProvider(Provider):
    name = "anthropic"

    def __init__(self, api_key: str, model: str, timeout: int = 300):
        self.api_key, self.model, self.timeout = api_key, model, timeout

    def generate(self, system: str, user: str, max_tokens: int = 8000) -> str:
        payload = {
            "model": self.model,
            "max_tokens": max_tokens,
            "system": system,
            "messages": [{"role": "user", "content": user}],
        }
        headers = {"x-api-key": self.api_key, "anthropic-version": API_VERSION, "content-type": "application/json"}
        last_error = None
        for attempt in range(3):
            try:
                r = requests.post(API_URL, json=payload, headers=headers, timeout=self.timeout)
            except requests.RequestException as e:
                last_error = f"No se ha podido conectar con la API ({type(e).__name__})."
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 200:
                data = r.json()
                text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
                if data.get("stop_reason") == "max_tokens":
                    text += "\n\n> Aviso: la respuesta se cortó por longitud. Regenera por partes."
                return text
            if r.status_code in (429, 500, 502, 503, 529):
                last_error = f"La API está saturada o ha fallado (código {r.status_code})."
                time.sleep(2 ** (attempt + 1))
                continue
            if r.status_code == 401:
                raise ProviderError("La clave de la API no es válida (error 401). Revisa el archivo .env.")
            raise ProviderError(f"La API ha devuelto un error {r.status_code}: {r.text[:300]}")
        raise ProviderError(last_error or "Error desconocido de la API. Prueba a reintentar.")
