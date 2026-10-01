"""Proveedores de modelos. Formato de especificación: ``proveedor:modelo``."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from modelduel.providers.base import DEFAULT_RETRIES, Provider, ProviderError, Response
from modelduel.providers.gemini import GeminiProvider
from modelduel.providers.openai_compat import OmniRouteProvider, OpenAIProvider
from modelduel.providers.replay import ReplayProvider

PROVIDERS = ("replay", "gemini", "openai", "omniroute")

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


def get_provider(
    spec: str,
    replay_dirs: list[Path] | None = None,
    retries: int = DEFAULT_RETRIES,
    on_retry: Callable[[str], None] | None = None,
) -> Provider:
    kind, model = parse_spec(spec)
    if kind == "replay":
        return ReplayProvider(model, replay_dirs)
    if kind == "gemini":
        return GeminiProvider(model, retries, on_retry)
    if kind == "omniroute":
        return OmniRouteProvider(model, retries, on_retry)
    return OpenAIProvider(model, retries, on_retry)
