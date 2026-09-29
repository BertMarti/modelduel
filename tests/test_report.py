import copy
import re

from modelduel.report import render_report, write_report
from modelduel.report.html import fmt_cost, fmt_seconds
from modelduel.results import summarize


def _attempt(passed, total, **extra):
    base = {
        "status": "ok",
        "passed": passed,
        "failed": total - passed,
        "errors": 0,
        "skipped": 0,
        "total": total,
        "solved": passed == total,
        "duration_s": 0.4,
        "output": "",
        "message": "",
        "latency_s": 1.5,
        "input_tokens": 100,
        "output_tokens": 50,
        "cost": 0.0001,
        "code": "def f():\n    return 1\n",
        "response": "",
        "run": 1,
    }
    base.update(extra)
    return base


RESULTS = {
    "schema": 1,
    "tool": "modelduel",
    "version": "0.1.0",
    "created_at": "2026-09-29T10:00:00+00:00",
    "runs": 1,
    "timeout_s": 20,
    "contenders": {
        "a": {"spec": "replay:alfa", "price": {"currency": "USD", "fictitious": True}},
        "b": {"spec": "openai:modelo-b", "price": None},
    },
    "tasks": [
        {
            "id": "suma",
            "title": "Sumar <b>números</b>",
            "difficulty": "fácil",
            "statement": "Enunciado",
            "tests_expected": 4,
            "results": {
                "a": [
                    _attempt(
                        4,
                        4,
                        code="print('<script>alert(1)</script>')\n",
                        output="assert '<script>' == 'x'",
                    )
                ],
                "b": [_attempt(1, 4, cost=None, input_tokens=None, output_tokens=None)],
            },
        }
    ],
}


def test_summarize():
    summary = summarize(RESULTS)
    assert summary["a"]["tests_passed"] == 4
    assert summary["a"]["tasks_solved"] == 1
    assert summary["b"]["tasks_solved"] == 0
    assert summary["a"]["cost"] == 0.0001
    assert summary["b"]["cost"] is None
    assert summary["b"]["input_tokens"] is None
    assert summary["a"]["fictitious_price"] is True


def test_el_informe_contiene_los_datos():
    html = render_report(copy.deepcopy(RESULTS))
    assert "replay:alfa" in html
    assert "openai:modelo-b" in html
    assert "Una sola ejecución es una señal débil" in html
    assert "4/4" in html and "1/4" in html
    assert "sin datos" in html
    assert "Precios ficticios" in html
    assert "<svg" in html
    assert "<details" in html


def test_el_informe_escapa_html_y_no_tiene_javascript():
    html = render_report(copy.deepcopy(RESULTS))
    assert "<script" not in html.lower()
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html
    assert "Sumar &lt;b&gt;números&lt;/b&gt;" in html


def test_varias_ejecuciones_cambia_la_advertencia():
    data = copy.deepcopy(RESULTS)
    data["runs"] = 3
    html = render_report(data)
    assert "3 ejecuciones por tarea" in html


def test_write_report(tmp_path):
    path = write_report(copy.deepcopy(RESULTS), tmp_path / "salida")
    assert path.name == "index.html"
    assert path.read_text(encoding="utf-8").startswith("<!doctype html>")


def test_formatos():
    assert fmt_seconds(1.24) == "1,2 s"
    assert fmt_seconds(75) == "1 min 15,0 s"
    assert fmt_seconds(None) == "sin datos"
    assert fmt_cost(None, "USD") == "sin datos"
    assert fmt_cost(0.00001, "USD") == "<0,0001 USD"
    assert fmt_cost(1234.5, "EUR") == "1.234,50 EUR"


# ---------------------------------------------------------------- revisión qa


def _hostile_results():
    """results.json manipulado: cualquier texto puede llegar al informe con ``report``."""
    data = copy.deepcopy(RESULTS)
    attempt = data["tasks"][0]["results"]["b"][0]
    attempt["status"] = "<img src=x onerror=alert(1)>"
    attempt["run"] = "<svg onload=alert(2)>"
    data["runs"] = 2
    data["created_at"] = "<fecha>"
    return data


def test_escapa_estado_ejecucion_y_fecha_de_un_results_manipulado():
    html = render_report(_hostile_results())
    assert "<img" not in html
    assert "<svg onload" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "&lt;fecha&gt;" in html
    assert "&amp;lt;" not in html  # sin doble escapado


def test_total_del_marcador_por_contendiente():
    data = copy.deepcopy(RESULTS)
    data["tasks"][0]["results"]["b"] = [_attempt(2, 5)]
    html = render_report(data)
    assert '<div class="big b">2<small>/5</small>' in html
    assert '<div class="big a">4<small>/4</small>' in html


def test_varias_ejecuciones_se_reflejan_en_el_informe():
    data = copy.deepcopy(RESULTS)
    data["runs"] = 2
    data["tasks"][0]["results"]["a"].append(_attempt(3, 4, run=2))
    data["tasks"][0]["results"]["b"].append(_attempt(4, 4, run=2))
    html = render_report(data)
    assert "Una sola ejecución" not in html  # el titular no contradice al texto
    assert "Intentos resueltos" in html
    assert "1/2" in html  # A resolvió 1 de sus 2 intentos
    assert "suma de 2 ejecuciones" in html
    assert "Ejecución 2" in html


def test_todas_las_graficas_svg_tienen_titulo_y_etiqueta():
    html = render_report(copy.deepcopy(RESULTS))
    svgs = re.findall(r"<svg\b[^>]*>.*?</svg>", html, flags=re.S)
    assert svgs
    for svg in svgs:
        assert 'role="img"' in svg and "aria-label=" in svg
        assert re.search(r"<title>[^<]+</title>", svg)


def test_filas_de_la_tabla_con_cabecera_de_fila():
    html = render_report(copy.deepcopy(RESULTS))
    tbody = html.split("<tbody>")[1].split("</tbody>")[0]
    assert tbody.count('<th scope="row"') == tbody.count("<tr>")
    assert '<td class="task"' not in tbody


def test_ganador_anunciado_a_lectores_de_pantalla_y_titular_legible():
    html = render_report(copy.deepcopy(RESULTS))
    assert '<span class="sr-only">(mejor)</span>' in html
    h1 = re.search(r"<h1>(.*?)</h1>", html, flags=re.S).group(1)
    assert re.sub(r"<[^>]+>", "", h1) == "alfa vs modelo-b"


def _hex_luminance(color: str) -> float:
    color = color.lstrip("#")
    channels = [int(color[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(fg: str, bg: str) -> float:
    hi, lo = sorted((_hex_luminance(fg), _hex_luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _blend(fg: str, bg: str, alpha: float) -> str:
    f = [int(fg.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    b = [int(bg.lstrip("#")[i : i + 2], 16) for i in (0, 2, 4)]
    return "#" + "".join(
        f"{round(x * alpha + y * (1 - alpha)):02x}" for x, y in zip(f, b, strict=True)
    )


def _css_vars(block: str) -> dict[str, str]:
    found = re.findall(r"--([\w-]+):\s*#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", block)
    return {name: "#" + (v if len(v) == 6 else "".join(c * 2 for c in v)) for name, v in found}


def test_contraste_aa_de_acentos_y_texto_atenuado():
    html = render_report(copy.deepcopy(RESULTS))
    screen = _css_vars(html.split(":root {")[1].split("}")[0])
    printed = _css_vars(html.split("@media print")[1].split("}")[0])
    for bg in ("bg", "panel"):
        for fg in ("a", "b", "text", "muted"):
            assert _contrast(screen[fg], screen[bg]) >= 4.5, (fg, bg)
    for fg in ("a", "b", "text", "muted"):
        assert _contrast(printed[fg], "#ffffff") >= 4.5, fg
    # El valor «perdedor» se atenúa: sigue cumpliendo AA y no atenúa el texto secundario.
    rule = re.search(r"\.metric \.val\.lose([^{]*)\{([^}]*)\}", html)
    assert rule and ".num" in rule.group(1), "la atenuación debe aplicarse solo al número"
    alpha = float(re.search(r"opacity:\s*([\d.]+)", rule.group(2)).group(1))
    for fg in ("a", "b"):
        assert _contrast(_blend(screen[fg], screen["bg"], alpha), screen["bg"]) >= 4.5, fg


def test_hoja_de_impresion_no_recorta_la_tabla():
    html = render_report(copy.deepcopy(RESULTS))
    printed = html.split("@media print")[1]
    assert re.search(r"\.table-wrap\s*\{[^}]*overflow:\s*visible", printed)
    assert re.search(r"th, td\s*\{[^}]*white-space:\s*normal", printed)


def test_informe_con_favicon_en_linea():
    html = render_report(copy.deepcopy(RESULTS))
    assert '<link rel="icon" href="data:image/svg+xml,' in html


def test_segundos_redondeados_sin_60():
    assert fmt_seconds(119.97) == "2 min 00,0 s"
    assert fmt_seconds(59.96) == "1 min 00,0 s"
