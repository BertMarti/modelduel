"""Proveedor ``gemini:<modelo>``: API REST ``generateContent`` de Google Generative Language."""

from __future__ import annotations

import os
import urllib.parse

from modelduel.providers.base import ProviderError, Response, as_int, post_json, require_env

DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


class GeminiProvider:
    def __init__(self, model: str) -> None:
        if not model:
            raise ProviderError("gemini necesita un modelo: gemini:<modelo>.")
        self.model = model
        self.spec = f"gemini:{model}"
        self.base_url = os.environ.get("GEMINI_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
        self.api_key = require_env(
            "GEMINI_API_KEY", "Crea una clave en Google AI Studio y expórtala en tu terminal."
        )

    def complete(self, prompt: str, *, task_id: str | None = None) -> Response:
        model = urllib.parse.quote(self.model, safe="-._")
        url = f"{self.base_url}/models/{model}:generateContent"
        payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
        # La clave va en una cabecera, no en la URL, para que no aparezca en errores ni logs.
        data, latency = post_json(
            url, payload, {"x-goog-api-key": self.api_key}, secrets=(self.api_key,)
        )
        return parse_gemini_response(data, latency)


def parse_gemini_response(data: dict, latency: float) -> Response:
    candidates = data.get("candidates") or []
    if not candidates:
        reason = (data.get("promptFeedback") or {}).get("blockReason", "sin candidatos")
        raise ProviderError(f"Gemini no devolvió respuesta ({reason}).")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    text = "".join(p.get("text", "") for p in parts if not p.get("thought"))
    usage = data.get("usageMetadata") or {}
    output = as_int(usage.get("candidatesTokenCount"))
    thoughts = as_int(usage.get("thoughtsTokenCount")) or 0
    return Response(
        text=text,
        input_tokens=as_int(usage.get("promptTokenCount")),
        # Los tokens de razonamiento se facturan como salida.
        output_tokens=None if output is None else output + thoughts,
        latency_s=latency,
    )
