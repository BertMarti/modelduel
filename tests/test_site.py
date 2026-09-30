"""Comprobaciones estáticas de la web del proyecto (site/index.html)."""

import re
from html.parser import HTMLParser

from tests.conftest import ROOT

SITE = ROOT / "site" / "index.html"


class _Collector(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags: list[tuple[str, dict]] = []
        self.ids: set[str] = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        self.tags.append((tag, attrs))
        if "id" in attrs:
            self.ids.add(attrs["id"])


def _parse() -> tuple[str, _Collector]:
    html = SITE.read_text(encoding="utf-8")
    collector = _Collector()
    collector.feed(html)
    return html, collector


def _meta(collector, key, value):
    return [a.get("content") for t, a in collector.tags if t == "meta" and a.get(key) == value]


def test_idioma_y_metadatos():
    html, c = _parse()
    assert '<html lang="es">' in html
    assert _meta(c, "name", "description")[0]
    for prop in ("og:title", "og:description", "og:type", "og:url", "og:locale"):
        assert _meta(c, "property", prop), prop
    assert _meta(c, "property", "og:url")[0] == "https://bertmarti.github.io/modelduel/"
    icons = [a for t, a in c.tags if t == "link" and a.get("rel") == "icon"]
    assert icons and icons[0]["href"].startswith("data:image/svg+xml,")


def test_enlaces_internos_y_externos():
    _, c = _parse()
    hrefs = [a["href"] for t, a in c.tags if t == "a"]
    for href in hrefs:
        if href.startswith("#"):
            assert href[1:] in c.ids, f"ancla rota: {href}"
        else:
            assert href == "demo/" or href.startswith("https://github.com/BertMarti/modelduel")
    assert "demo/" in hrefs


def test_accesibilidad_basica():
    html, c = _parse()
    h1 = re.search(r"<h1>(.*?)</h1>", html, flags=re.S).group(1)
    assert re.sub(r"<[^>]+>", "", h1) == "modelo vs modelo"
    tbody = html.split("<tbody>")[1].split("</tbody>")[0]
    assert tbody.count('<th scope="row"') == tbody.count("<tr>")
    assert all(a.get("scope") for t, a in c.tags if t == "th")
    assert any(t == "a" and a.get("class") == "skip" for t, a in c.tags), (
        "falta el salto al contenido"
    )
