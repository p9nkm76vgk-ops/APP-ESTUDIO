"""Proveedores de IA intercambiables.

Para añadir otro proveedor (OpenAI, Gemini, un modelo local...), crea una clase con el mismo
método `generate(system, user, max_tokens) -> str` y regístrala en `get_provider`.
"""
from __future__ import annotations

import os

from .base import Provider, ProviderError
from .offline import OfflineProvider


def get_provider(name: str = "auto", model: str = "claude-sonnet-5-5") -> Provider:
    from .anthropic_api import AnthropicProvider

    key = os.environ.get("ESTUDIO_ANTHROPIC_API_KEY", "").strip()
    if name == "anthropic" or (name == "auto" and key):
        if not key:
            raise ProviderError(
                "Falta la clave de la API de Anthropic. Crea el archivo .env con "
                "ESTUDIO_ANTHROPIC_API_KEY=... (ver .env.example) o usa el modo sin IA."
            )
        return AnthropicProvider(api_key=key, model=model)
    return OfflineProvider()


__all__ = ["Provider", "ProviderError", "get_provider", "OfflineProvider"]
