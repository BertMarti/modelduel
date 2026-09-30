"""Proveedores de modelos. Formato de especificación: ``proveedor:modelo``."""

from __future__ import annotations

from pathlib import Path

from modelduel.providers.base import Provider, ProviderError, Response
from modelduel.providers.gemini import GeminiProvider
from modelduel.providers.openai_compat import OpenAIProvider
from modelduel.providers.replay import ReplayProvider

PROVIDERS = ("replay", "gemini", "openai")

__all__ = ["Provider", "ProviderError", "Response", "get_provider", "parse_spec", "PROVIDERS"]


def parse_spec(spec: str) -> tuple[str, str]:
    kind, sep, model = spec.partition(":")
    kind = kind.strip().lower()
    model = model.strip()
    if not sep or not model:
        raise ProviderError(f"Especificación «{spec}» no válida: usa proveedor:modelo.")
    if kind not in PROVIDERS:
        raise ProviderError(f"Proveedor «{kind}» desconocido. Disponibles: {', '.join(PROVIDERS)}.")
    return kind, model


def get_provider(spec: str, replay_dirs: list[Path] | None = None) -> Provider:
    kind, model = parse_spec(spec)
    if kind == "replay":
        return ReplayProvider(model, replay_dirs)
    if kind == "gemini":
        return GeminiProvider(model)
    return OpenAIProvider(model)
