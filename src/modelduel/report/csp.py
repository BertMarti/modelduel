"""CSP sin ``'unsafe-inline'``: cada ``<style>`` se autoriza por su hash SHA-256.

Todas las webs de Pages de BertMarti comparten el origen ``https://bertmarti.github.io``; con
``style-src 'unsafe-inline'`` una inyección de HTML podría meter estilos propios (y con ellos
filtrar datos por CSS). Los informes siguen siendo un único archivo: la plantilla deja
``STYLE_HASHES`` en la CSP y ``apply_style_hashes`` lo sustituye por el hash de sus estilos.
"""

from __future__ import annotations

import base64
import hashlib
import re

STYLE_HASHES = "__MODELDUEL_STYLE_HASHES__"
_STYLE = re.compile(r"<style>(.*?)</style>", re.S)


def style_hashes(html: str) -> str:
    """Fuentes CSP (``'sha256-…'``) de los ``<style>`` de ``html``, en orden y sin repetir."""
    tokens: list[str] = []
    for css in _STYLE.findall(html):
        # El navegador calcula el hash del texto ya normalizado (CRLF -> LF).
        text = css.replace("\r\n", "\n").replace("\r", "\n")
        digest = base64.b64encode(hashlib.sha256(text.encode("utf-8")).digest()).decode("ascii")
        token = f"'sha256-{digest}'"
        if token not in tokens:
            tokens.append(token)
    return " ".join(tokens) or "'none'"


def apply_style_hashes(html: str) -> str:
    """Sustituye la primera ``STYLE_HASHES`` (la de la CSP, en ``<head>``) por los hashes."""
    return html.replace(STYLE_HASHES, style_hashes(html), 1)
