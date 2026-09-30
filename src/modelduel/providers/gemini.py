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


def parse_gemini_response(data: object, latency: float) -> Response:
    if not isinstance(data, dict):
        raise ProviderError("Gemini devolvió una respuesta con un formato inesperado.")
    candidates = data.get("candidates") or []
    if not candidates:
        feedback = data.get("promptFeedback")
        reason = feedback.get("blockReason") if isinstance(feedback, dict) else None
        raise ProviderError(f"Gemini no devolvió respuesta ({reason or 'sin candidatos'}).")
    first = candidates[0]
    if not isinstance(first, dict):
        raise ProviderError("Gemini devolvió un candidato con un formato inesperado.")
    content = first.get("content")
    parts = content.get("parts") if isinstance(content, dict) else None
    text = "".join(
        str(p.get("text") or "")
        for p in parts or []
        if isinstance(p, dict) and not p.get("thought")
    )
    if not text.strip():
        # SAFETY, RECITATION, MAX_TOKENS (todo el presupuesto en razonamiento)...
        reason = first.get("finishReason") or "sin texto"
        raise ProviderError(f"Gemini no devolvió texto (finishReason: {reason}).")
    usage = data.get("usageMetadata")
    usage = usage if isinstance(usage, dict) else {}
    output = as_int(usage.get("candidatesTokenCount"))
    thoughts = as_int(usage.get("thoughtsTokenCount")) or 0
    return Response(
        text=text,
        input_tokens=as_int(usage.get("promptTokenCount")),
        # Los tokens de razonamiento se facturan como salida.
        output_tokens=None if output is None else output + thoughts,
        latency_s=latency,
    )
