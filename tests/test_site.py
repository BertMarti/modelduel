"""Comprobaciones estáticas de la web del proyecto (site/index.html)."""

import json
import re
import shutil
import struct
import subprocess
from html.parser import HTMLParser

import pytest

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


# ---------------------------------------------------------------- duelo en directo

DEMO_JS = ROOT / "site" / "demo.js"


def _section_demo(html: str) -> str:
    return html.split('<section id="demo"')[1].split("</section>")[0]


def test_la_seccion_demo_existe_con_el_boton_primario_y_anuncio_solo_de_fases():
    html, c = _parse()
    assert "demo" in c.ids
    section = _section_demo(html)
    assert 'aria-labelledby="demo-titulo"' in html
    assert re.search(r'<button[^>]*id="demo-main"[^>]*>Ver un duelo en directo</button>', section)
    assert "btn primary" in re.search(r'<button[^>]*id="demo-main"[^>]*>', section).group(0)
    assert "pregrabado" in section.lower()
    live = re.search(r'<[^>]*id="demo-live"[^>]*>', section).group(0)
    assert 'aria-live="polite"' in live
    assert section.count("aria-live") == 1, "aria-live solo para los cambios de fase"
    # Detener existe y empieza oculto; los controles solo se muestran con JavaScript.
    assert re.search(r'<button[^>]*id="demo-stop"[^>]*hidden', section)
    assert 'class="demo-controls" hidden' in section


def test_la_portada_enlaza_al_duelo_en_directo():
    html, c = _parse()
    primarias = [a for t, a in c.tags if t == "a" and "primary" in a.get("class", "").split()]
    assert primarias[0]["href"] == "#demo"
    nav = html.split('<nav aria-label="Principal">')[1].split("</nav>")[0]
    assert 'href="#demo"' in nav


def test_sin_javascript_queda_un_enlace_al_informe_estatico():
    html, _ = _parse()
    section = _section_demo(html)
    nojs = re.search(r'<p class="demo-nojs">(.*?)</p>', section, flags=re.S).group(1)
    assert 'href="demo/"' in nojs
    assert 'href="demo/"' in section.split("demo-foot")[1]


def test_un_unico_script_propio_y_diferido():
    html, c = _parse()
    scripts = [a for t, a in c.tags if t == "script"]
    assert scripts == [{"src": "demo.js", "defer": None}]
    assert "<script>" not in html and "onclick" not in html


def test_el_script_no_usa_html_ni_carga_nada_de_fuera():
    js = DEMO_JS.read_text(encoding="utf-8")
    for peligroso in ("innerHTML", "outerHTML", "insertAdjacentHTML", "document.write", "eval("):
        assert peligroso not in js, peligroso
    assert "visibilitychange" in js and "prefers-reduced-motion" in js
    assert js.count("fetch(") == 1 and 'fetch("demo/results.json"' in js
    assert not re.search(r"https?://", js), "el script no habla con ningún servidor"
    assert "setInterval(" in js and "requestAnimationFrame" not in js


def test_el_css_respeta_movimiento_reducido_y_foco():
    html, _ = _parse()
    css = html.split("<style>")[1].split("</style>")[0]
    assert "prefers-reduced-motion" in css
    assert ".demo-code:focus-visible" in css and "button:focus-visible" in css


def test_results_json_generado_en_el_ci_se_puede_reproducir(tmp_path):
    """El sitio se genera con replay: la forma de results.json es el contrato de demo.js."""
    from modelduel.cli import main

    out = tmp_path / "demo"
    args = ["run", str(ROOT / "examples" / "tasks")]
    for name in ("alfa", "beta", "gamma"):
        args += ["--model", f"replay:{name}"]
    assert main([*args, "--out", str(out)]) == 0
    data = json.loads((out / "results.json").read_text(encoding="utf-8"))
    attempt = data["tasks"][0]["results"]["a"][0]
    for key in ("code", "latency_s", "input_tokens", "output_tokens", "passed", "total", "output"):
        assert key in attempt, key
    assert data["tasks"][0]["statement"]
    if shutil.which("node") is None:
        pytest.skip("Node no está instalado: no se prueba demo.js con los datos reales")
    script = (
        "const c=require(process.argv[1]);"
        "const d=JSON.parse(require('fs').readFileSync(process.argv[2],'utf8'));"
        "const p=c.prepare(d);const v=c.verdict(p);"
        "console.log(JSON.stringify({sides:p.sides.map(s=>[s.side,s.passed,s.total,s.code.length>0]),"
        "marks:p.sides.map(s=>s.marks.length),top:v.rows[0].side,text:v.text,marks0:v.rows[0].mark}))"
    )
    done = subprocess.run(
        ["node", "-e", script, str(DEMO_JS), str(out / "results.json")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=True,
    )
    result = json.loads(done.stdout)
    assert [s[0] for s in result["sides"]] == ["a", "b", "c"]
    assert all(s[3] for s in result["sides"]), "cada contendiente trae su código grabado"
    assert result["marks"] == [s[2] for s in result["sides"]]
    # A y C resuelven la tarea; C es la más rápida. El informe completo puede ordenar distinto
    # (agrega todas las tareas), así que el veredicto del directo habla solo de esta tarea.
    assert result["top"] == "c"
    assert result["marks0"] == "▲ primero"
    assert result["text"].startswith(
        "En esta tarea («" + data["tasks"][0]["title"] + "», 1 de 3), gana C"
    )


def test_el_fallo_de_carga_se_anuncia_y_la_salvedad_del_informe_esta_en_el_script():
    html, _ = _parse()
    assert re.search(r'<p id="demo-error"[^>]*role="alert"', html)
    js = DEMO_JS.read_text(encoding="utf-8")
    assert "El informe completo agrega todas las tareas y puede dar otro orden." in js
    assert "(recortado)" in js and "mostrando" in js


def test_contraste_aa_de_toda_la_paleta_de_la_portada():
    from tests.test_report import _contrast, _css_vars

    html, _ = _parse()
    css = html.split("<style>")[1].split("</style>")[0]
    screen = _css_vars(css.split(":root {")[1].split("}")[0])
    printed = _css_vars(css.split("@media print")[1].split("}")[0])
    accents = ("a", "b", "c", "d", "e", "f")
    for fg in (*accents, "text", "muted"):
        for bg in ("bg", "panel"):
            assert _contrast(screen[fg], screen[bg]) >= 4.5, (fg, bg)
    for fg in (*accents, "text", "muted"):
        assert _contrast(printed[fg], "#ffffff") >= 4.5, fg
    # Los acentos d, e y f no se repiten como colores sueltos fuera de las variables.
    assert "#ffb833" not in css.split(":root {")[1].split("}")[1]


def test_imagen_social_og_y_twitter_card():
    _, c = _parse()
    url = "https://bertmarti.github.io/modelduel/og.png"
    assert _meta(c, "property", "og:image")[0] == url
    assert _meta(c, "property", "og:image:width")[0] == "1200"
    assert _meta(c, "property", "og:image:height")[0] == "630"
    assert _meta(c, "property", "og:image:alt")[0]
    assert _meta(c, "name", "twitter:card")[0] == "summary_large_image"


def test_og_png_existe_con_1200_por_630_y_pesa_poco():
    png = (ROOT / "site" / "og.png").read_bytes()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    width, height = struct.unpack(">II", png[16:24])  # cabecera IHDR
    assert (width, height) == (1200, 630)
    assert len(png) < 200_000
