import copy

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
