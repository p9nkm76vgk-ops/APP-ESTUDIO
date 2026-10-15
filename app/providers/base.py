from __future__ import annotations


class ProviderError(Exception):
    """Error del proveedor de IA, con un mensaje comprensible."""


class Provider:
    name = "base"
    uses_ai = True

    def generate(self, system: str, user: str, max_tokens: int = 8000) -> str:  # pragma: no cover
        raise NotImplementedError
