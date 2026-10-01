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
            assert href in ("demo/", "leaderboard/") or href.startswith(
                "https://github.com/BertMarti/modelduel"
            )
    assert "demo/" in hrefs
    assert "leaderboard/" in hrefs


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


def test_jerarquia_de_llamadas_a_la_accion_y_navegacion():
    html, c = _parse()
    nav = html.split('<nav aria-label="Principal">')[1].split("</nav>")[0]
    assert nav.count("<a ") <= 5, "la navegación principal debe ser corta"
    primarias = [a for t, a in c.tags if t == "a" and "primary" in a.get("class", "").split()]
    assert len(primarias) == 1, "solo una llamada a la acción primaria"
    assert "duel-bars" not in html, "las barras fijas de la portada se retiraron"


def test_tabla_de_proveedores_es_una_region_desplazable_accesible():
    _, c = _parse()
    wraps = [a for t, a in c.tags if t == "div" and a.get("class") == "table-wrap"]
    assert wraps
    for a in wraps:
        assert a.get("tabindex") == "0"
        assert a.get("role") == "region"
        assert a.get("aria-label")
    html = SITE.read_text(encoding="utf-8")
    assert ".table-wrap:focus-visible" in html and "a:focus-visible" in html


def test_ningun_texto_de_la_portada_baja_de_12_px():
    html = SITE.read_text(encoding="utf-8")
    css = html.split("<style>")[1].split("</style>")[0].split("@media print")[0]
    sizes = re.findall(r"font(?:-size)?:\s*(?:[\w.]+\s+)?(\d+(?:\.\d+)?)px", css)
    assert sizes and min(float(s) for s in sizes) >= 12
