"""Liga de 2 a 6 contendientes: CLI, clasificación e informe (sin red)."""

from __future__ import annotations

import argparse
import copy
import itertools
import json
import re
import shutil

import pytest

from modelduel.cli import collect_specs, main, scoreboard
from modelduel.duel import run_duel
from modelduel.providers import Response
from modelduel.report import render_report
from modelduel.results import ALL_SIDES, load_results, rank_sides, sides_of, summarize
from modelduel.resume import plan_resume
from tests.conftest import ADD_TESTS
from tests.test_report import _contrast, _css_vars

CORRECT = "```python\ndef add(a, b):\n    return a + b\n```"
WRONG = "```python\ndef add(a, b):\n    return 0\n```"


class Fixed:
    def __init__(self, spec, answer=CORRECT, tokens=(10, 5)):
        self.spec = spec
        self.answer = answer
        self.tokens = tokens

    def complete(self, prompt, *, task_id=None):
        return Response(self.answer, self.tokens[0], self.tokens[1], 0.5)


_COUNTER = itertools.count()


def _league(make_task, n, runs=1, answers=None, prices=None):
    task = make_task(ADD_TESTS, name=f"suma{next(_COUNTER)}")
    answers = answers or {}
    providers = {side: Fixed(f"fake:m{side}", answers.get(side, CORRECT)) for side in ALL_SIDES[:n]}
    return run_duel([task], providers, prices or {}, runs=runs)


# ---------------------------------------------------------------- clasificación


def _summary(**sides):
    return {
        side: {
            "tasks_solved": solved,
            "tests_passed": tests,
            "cost": cost,
            "currency": currency,
        }
        for side, (solved, tests, cost, currency) in sides.items()
    }


def test_clasificacion_por_tareas_luego_tests_luego_coste():
    summary = _summary(
        a=(2, 10, 5.0, "USD"),
        b=(3, 8, 9.0, "USD"),  # más tareas: gana aunque tenga menos tests
        c=(2, 12, 7.0, "USD"),  # mismas tareas que A pero más tests
        d=(2, 10, 1.0, "USD"),  # empata con A en todo salvo el coste
    )
    assert rank_sides(summary) == [(1, "b"), (2, "c"), (3, "d"), (4, "a")]


def test_empates_completos_comparten_posicion_y_conservan_el_orden():
    summary = _summary(
        a=(1, 5, 1.0, "USD"), b=(2, 9, 1.0, "USD"), c=(1, 5, 1.0, "USD"), d=(2, 9, 1.0, "USD")
    )
    assert rank_sides(summary) == [(1, "b"), (1, "d"), (3, "a"), (3, "c")]


def test_el_coste_solo_desempata_si_todos_tienen_precio_en_la_misma_moneda():
    sin_precio = _summary(a=(1, 5, None, None), b=(1, 5, 0.1, "USD"))
    assert rank_sides(sin_precio) == [(1, "a"), (1, "b")]
    monedas = _summary(a=(1, 5, 9.0, "USD"), b=(1, 5, 0.1, "EUR"))
    assert rank_sides(monedas) == [(1, "a"), (1, "b")]


def test_summarize_y_sides_of_con_seis(make_task):
    results = _league(make_task, 6, answers={"c": WRONG, "f": WRONG})
    assert sides_of(results) == list(ALL_SIDES)
    summary = results["summary"]
    assert list(summary) == list(ALL_SIDES)
    assert summary["a"]["tasks_solved"] == 1 and summary["c"]["tasks_solved"] == 0
    assert summarize(results) == summary
    ranking = rank_sides(summary)
    assert [side for _pos, side in ranking] == ["a", "b", "d", "e", "c", "f"]
    assert [pos for pos, _side in ranking] == [1, 1, 1, 1, 5, 5]


def test_resultados_de_v010_siguen_siendo_dos_lados():
    old = {"contenders": {"a": {"spec": "x:a"}, "b": {"spec": "x:b"}}, "tasks": []}
    assert sides_of(old) == ["a", "b"]
    assert sides_of({}) == []


# ---------------------------------------------------------------- CLI


def _args(a=None, b=None, model=()):
    return argparse.Namespace(a=a, b=b, model=list(model))


def test_collect_specs_compatible_con_v010_y_con_model():
    assert collect_specs(_args("x:1", "y:2")) == ["x:1", "y:2"]
    assert collect_specs(_args(model=["x:1", "y:2", "z:3"])) == ["x:1", "y:2", "z:3"]
    assert collect_specs(_args("x:1", "y:2", ["z:3", "w:4"])) == ["x:1", "y:2", "z:3", "w:4"]
    assert collect_specs(_args("x:1", model=["y:2"])) == ["x:1", "y:2"]


def test_collect_specs_errores():
    from modelduel.tasks import TaskError

    for bad, message in (
        (_args(), "al menos 2"),
        (_args("x:1"), "al menos 2"),
        (_args(model=["x:1"]), "al menos 2"),
        (_args(b="y:2", model=["x:1"]), "--b necesita también --a"),
        (_args("a:1", "b:2", [f"m:{i}" for i in range(5)]), "máximo 6"),
    ):
        with pytest.raises(TaskError, match=message):
            collect_specs(_args_copy(bad))


def _args_copy(args):
    return copy.copy(args)


@pytest.fixture
def replays(tmp_path, examples_dir):
    """Seis contendientes replay (copias de las tres grabaciones con otro nombre)."""
    base = tmp_path / "replays"
    for name, source in (
        ("alfa", "alfa"),
        ("beta", "beta"),
        ("gamma", "gamma"),
        ("delta", "alfa"),
        ("epsilon", "beta"),
        ("zeta", "gamma"),
    ):
        shutil.copytree(examples_dir / "replays" / source, base / name)
    return base


def _run(examples_dir, replays, out, *models, extra=(), task="tasks"):
    argv = ["run", str(examples_dir / task), "--replays", str(replays), "--out", str(out)]
    for model in models:
        argv += ["--model", f"replay:{model}"]
    return main([*argv, *extra])


def test_liga_de_tres_de_extremo_a_extremo(examples_dir, replays, tmp_path, capsys):
    out = tmp_path / "liga"
    assert _run(examples_dir, replays, out, "alfa", "beta", "gamma") == 0
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert list(results["contenders"]) == ["a", "b", "c"]
    assert results["contenders"]["c"]["spec"] == "replay:gamma"
    assert results["status"] == "complete"
    printed = capsys.readouterr().out
    lines = [ln for ln in printed.splitlines() if re.match(r"\s+\d+\s+[A-F] replay:", ln)]
    assert [ln.split()[2] for ln in lines] == ["replay:alfa", "replay:gamma", "replay:beta"]
    assert [ln.split()[0] for ln in lines] == ["1", "2", "3"]
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "Informe de liga" in html and "Clasificación" in html
    assert "<script" not in html.lower()


def test_liga_de_seis_y_varias_ejecuciones(examples_dir, replays, tmp_path):
    out = tmp_path / "seis"
    models = ("alfa", "beta", "gamma", "delta", "epsilon", "zeta")
    assert (
        _run(examples_dir, replays, out, *models, extra=("--runs", "2"), task="tasks/slugify") == 0
    )
    results = load_results(out / "results.json")
    assert sides_of(results) == list(ALL_SIDES)
    assert all(len(t["results"][s]) == 2 for t in results["tasks"] for s in ALL_SIDES)
    assert len(results["tasks"]) == 1
    html = (out / "index.html").read_text(encoding="utf-8")
    assert "Intentos resueltos" in html and "6 contendientes" in html


def test_a_b_y_model_se_pueden_mezclar_y_a_b_sigue_dando_un_duelo(examples_dir, replays, tmp_path):
    out = tmp_path / "mezcla"
    argv = ["run", str(examples_dir / "tasks"), "--replays", str(replays), "--out", str(out)]
    assert main([*argv, "--a", "replay:alfa", "--b", "replay:beta", "-m", "replay:gamma"]) == 0
    assert list(load_results(out / "results.json")["contenders"]) == ["a", "b", "c"]
    duel = tmp_path / "duelo"
    argv[-1] = str(duel)
    assert main([*argv, "--a", "replay:alfa", "--b", "replay:beta"]) == 0
    html = (duel / "index.html").read_text(encoding="utf-8")
    assert "Informe de duelo" in html and "Informe de liga" not in html


def test_cli_rechaza_pocos_muchos_y_repetidos(examples_dir, replays, tmp_path, capsys):
    tasks = str(examples_dir / "tasks")
    base = ["run", tasks, "--replays", str(replays), "--out", str(tmp_path / "x")]
    assert main([*base, "--model", "replay:alfa"]) == 2
    assert "al menos 2" in capsys.readouterr().err
    seven = [
        arg
        for m in ("alfa", "beta", "gamma", "delta", "epsilon", "zeta", "alfa")
        for arg in ("-m", f"replay:{m}")
    ]
    assert main([*base, *seven]) == 2
    assert "máximo 6" in capsys.readouterr().err
    assert main([*base, "--a", "replay:alfa", "--model", "replay:alfa"]) == 2
    err = capsys.readouterr().err
    assert "aparece dos veces" in err and "--runs" in err
    assert not (tmp_path / "x" / "results.json").exists()


def test_reanudar_una_liga(make_task):
    task = make_task(ADD_TESTS)
    providers = {side: Fixed(f"fake:m{side}") for side in "abc"}
    first = run_duel([task], providers, {})
    specs = {side: p.spec for side, p in providers.items()}
    reuse, warnings = plan_resume(first, [task], specs, 1, first["timeout_s"])
    assert len(reuse) == 3 and warnings == []
    again = run_duel([task], providers, {}, reuse=reuse)
    assert again["summary"] == first["summary"] or again["summary"]["c"]["tasks_solved"] == 1


def test_scoreboard_con_precios_ficticios(make_task):
    from modelduel.pricing import Price

    prices = {
        "fake:ma": Price(1.0, 2.0, fictitious=True),
        "fake:mb": Price(1.0, 2.0, fictitious=True),
    }
    results = _league(make_task, 3, prices=prices)
    text = scoreboard(results)
    assert "precios ficticios" in text
    assert text.count("fake:m") == 3


# ---------------------------------------------------------------- informe


def _html(make_task, n, **kwargs):
    return render_report(_league(make_task, n, **kwargs))


@pytest.mark.parametrize("n", [2, 3, 4, 5, 6])
def test_el_informe_se_genera_con_2_a_6_contendientes(make_task, n):
    html = _html(make_task, n, answers={"b": WRONG})
    assert ("Informe de duelo" in html) == (n == 2)
    assert ("Informe de liga" in html) == (n > 2)
    assert "<script" not in html.lower()
    for side in ALL_SIDES[:n]:
        assert f"fake:m{side}" in html
    for side in ALL_SIDES[n:]:
        assert f"fake:m{side}" not in html
    h1 = re.search(r"<h1>(.*?)</h1>", html, flags=re.S).group(1)
    assert re.sub(r"<[^>]+>", "", h1) == " vs ".join(f"m{s}" for s in ALL_SIDES[:n])


def test_la_liga_tiene_clasificacion_matriz_y_etiquetas_accesibles(make_task):
    html = _html(make_task, 4, answers={"c": WRONG})
    ranking = html.split('<table class="ranking">')[1].split("</table>")[0]
    assert ranking.count('<th scope="row"') == 4
    assert "(mejor)" in ranking
    matrix = html.split('<table class="matrix">')[1].split("</table>")[0]
    assert matrix.count('<th scope="col"') == 5  # tarea + 4 contendientes
    body = matrix.split("<tbody>")[1].split("</tbody>")[0]
    assert body.count('<th scope="row"') == body.count("<tr>")
    assert "resuelta" in matrix and "no resuelta" in matrix
    for letter in "ABCD":  # el color nunca es la única pista
        assert f'class="tag {letter.lower()}">{letter}</span>' in html
    svgs = re.findall(r"<svg\b[^>]*>.*?</svg>", html, flags=re.S)
    assert len(svgs) > 10
    for svg in svgs:
        assert 'role="img"' in svg and "aria-label=" in svg
        assert re.search(r"<title>[^<]+</title>", svg)


def test_la_liga_anuncia_empates_y_lider(make_task):
    solo = _html(make_task, 3, answers={"b": WRONG, "c": WRONG})
    assert "Primero:" in solo and "Empate" not in solo
    empate = _html(make_task, 3)
    assert "Empate en cabeza:" in empate


def test_la_liga_escapa_html_de_un_results_manipulado(make_task):
    results = _league(make_task, 3)
    results["contenders"]["c"]["spec"] = "x:<img src=x onerror=alert(1)>"
    results["tasks"][0]["title"] = "<b>t</b>"
    html = render_report(results)
    assert "<img" not in html and "<b>t</b>" not in html
    assert "&lt;img src=x onerror=alert(1)&gt;" in html
    assert "&amp;lt;" not in html


def test_liga_incompleta_se_avisa_y_no_rompe(make_task):
    results = _league(make_task, 3, runs=2)
    results["status"] = "in_progress"
    del results["tasks"][0]["results"]["c"][1]
    results["tasks"][0]["results"]["b"] = []
    results["summary"] = summarize(results)
    html = render_report(results)
    assert "Duelo incompleto: 3 de 6 intentos" in html
    assert "sin hacer" in html


def test_comparativa_no_marca_ganador_si_todos_empatan_ni_mezcla_monedas(make_task):
    from modelduel.pricing import Price

    prices = {
        "fake:ma": Price(1.0, 2.0, "USD"),
        "fake:mb": Price(1.0, 2.0, "EUR"),
        "fake:mc": Price(1.0, 2.0, "USD"),
    }
    html = _html(make_task, 3, prices=prices)
    assert "monedas distintas: no comparables" in html
    tasks_block = html.split("<h3>Tareas resueltas</h3>")[1].split("</div></div>")[0]
    assert "(mejor)" not in tasks_block  # empate total


def test_paleta_ampliada_cumple_contraste_aa(make_task):
    html = _html(make_task, 6)
    screen = _css_vars(html.split(":root {")[1].split("}")[0])
    printed = _css_vars(html.split("@media print")[1].split("}")[0])
    letters = list(ALL_SIDES)
    assert len({screen[s] for s in letters}) == 6  # seis colores distintos
    assert len({printed[s] for s in letters}) == 6
    for side in letters:
        for bg in ("bg", "panel"):
            assert _contrast(screen[side], screen[bg]) >= 4.5, (side, bg)
        assert _contrast(printed[side], "#ffffff") >= 4.5, side
        assert _contrast(printed[side], printed["panel"]) >= 4.5, side
        for rule in (rf"\.{side}\s*\{{", rf"\.fill-{side}\s*\{{"):
            assert re.search(rule, html), rule


def test_la_hoja_de_impresion_de_la_liga_no_recorta_tablas(make_task):
    html = _html(make_task, 6)
    printed = html.split("@media print")[1]
    assert re.search(r"\.table-wrap\s*\{[^}]*overflow:\s*visible", printed)
    assert "print-color-adjust: exact" in printed
    assert ".matrix svg" in printed and ".lg-row svg" in printed


def test_los_resultados_de_v010_siguen_renderizando_como_duelo():
    from tests.test_report import RESULTS

    html = render_report(copy.deepcopy(RESULTS))
    assert "Informe de duelo" in html and 'class="board"' in html
