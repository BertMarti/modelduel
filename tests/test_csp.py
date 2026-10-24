"""La Content-Security-Policy de los informes y de la portada (v0.8.0).

Es una defensa en profundidad frente a XSS con salidas de modelos: aunque el escape fallara,
un informe no puede ejecutar JavaScript ni cargar nada de fuera.
"""

from __future__ import annotations

import copy
import json
from html.parser import HTMLParser

import pytest

from modelduel.leaderboard import build_leaderboard
from modelduel.report import render_report
from tests.conftest import ROOT

REPORT_CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; img-src data:; "
    "base-uri 'none'; form-action 'none'"
)
DUEL = ROOT / "results" / "2026-10-01-duelo-alfa-beta.json"
LEAGUE = ROOT / "results" / "2026-10-01-liga-alfa-beta-gamma.json"


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.csp: list[tuple[str, list[str]]] = []  # (política, etiquetas de <head> previas)
        self.head: list[str] = []
        self.in_head = False
        self.scripts: list[dict[str, str | None]] = []
        self.blank_links: list[dict[str, str | None]] = []

    def handle_starttag(self, tag, attrs):
        data = dict(attrs)
        is_csp = (
            tag == "meta" and (data.get("http-equiv") or "").lower() == "content-security-policy"
        )
        if is_csp:
            before = list(self.head) if self.in_head else ["(fuera de head)"]
            self.csp.append((data.get("content") or "", before))
        if tag == "head":
            self.in_head = True
        elif self.in_head:
            self.head.append(tag)
        if tag == "script":
            self.scripts.append(data)
        if tag == "a" and data.get("target") == "_blank":
            self.blank_links.append(data)

    def handle_endtag(self, tag):
        if tag == "head":
            self.in_head = False


def _parse(html: str) -> _Collector:
    collector = _Collector()
    collector.feed(html)
    return collector


def _assert_report_csp(html: str) -> None:
    parsed = _parse(html)
    assert len(parsed.csp) == 1, parsed.csp
    policy, before = parsed.csp[0]
    assert policy == REPORT_CSP
    assert "script-src" not in policy and "unsafe-eval" not in policy
    # Dentro de <head> y antes del título y de los estilos.
    assert "(fuera de head)" not in before
    assert "title" not in before and "style" not in before
    assert not parsed.scripts
    assert all("noopener" in (link.get("rel") or "") for link in parsed.blank_links)


@pytest.mark.parametrize("path", [DUEL, LEAGUE], ids=["duelo", "liga"])
def test_los_informes_llevan_la_csp_sin_scripts(path):
    _assert_report_csp(render_report(json.loads(path.read_text(encoding="utf-8"))))


def test_la_clasificacion_y_sus_informes_llevan_la_csp(tmp_path):
    build_leaderboard(ROOT / "results", tmp_path / "lb")
    pages = sorted((tmp_path / "lb").rglob("index.html"))
    assert len(pages) >= 2  # la clasificación y al menos un informe de duelo
    for page in pages:
        _assert_report_csp(page.read_text(encoding="utf-8"))


def test_un_results_hostil_no_inyecta_scripts_y_conserva_la_csp():
    evil = copy.deepcopy(json.loads(DUEL.read_text(encoding="utf-8")))
    payload = "</style><script>alert(1)</script><meta http-equiv='refresh' content='0'>"
    evil["tasks"][0]["title"] = payload
    evil["tasks"][0]["statement"] = payload
    for side in evil["contenders"].values():
        side["spec"] = "x:" + payload
    parsed = _parse(render_report(evil))
    assert not parsed.scripts
    assert len(parsed.csp) == 1 and parsed.csp[0][0] == REPORT_CSP


def test_la_portada_tiene_una_csp_estricta_para_scripts():
    parsed = _parse((ROOT / "site" / "index.html").read_text(encoding="utf-8"))
    assert len(parsed.csp) == 1
    directives = {
        part.split()[0]: part.split()[1:]
        for part in (p.strip() for p in parsed.csp[0][0].split(";"))
        if part
    }
    assert directives["script-src"] == ["'self'"]
    assert directives["connect-src"] == ["'self'"]
    assert directives["object-src"] == ["'none'"]
    assert directives["form-action"] == ["'none'"]
    assert "'unsafe-eval'" not in sum(directives.values(), [])
    for script in parsed.scripts:
        src = script.get("src") or ""
        assert src and not src.startswith(("http:", "https:", "//")), script
    assert all("noopener" in (link.get("rel") or "") for link in parsed.blank_links)
