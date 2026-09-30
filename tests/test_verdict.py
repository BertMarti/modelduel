"""Veredicto del duelo de dos: usa la misma ordenación que la clasificación (#15)."""

import copy
import re

import pytest

from modelduel.report import render_report
from modelduel.results import decide, rank_sides
from tests.test_league import _summary
from tests.test_report import RESULTS, _attempt


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        # Antes discrepaban: B superaba más tests, pero A resolvía más tareas.
        ((2, 6, 1.0, "USD"), (1, 9, 1.0, "USD"), ("a", "tasks")),
        ((1, 9, 1.0, "USD"), (2, 6, 1.0, "USD"), ("b", "tasks")),
        ((2, 8, 9.0, "USD"), (2, 7, 1.0, "USD"), ("a", "tests")),  # más tests, aunque sea más caro
        ((2, 8, 3.0, "USD"), (2, 8, 1.0, "USD"), ("b", "cost")),
        ((2, 8, None, None), (2, 8, 1.0, "USD"), (None, None)),  # sin coste comparable: empate
        ((2, 8, 1.0, "USD"), (2, 8, 1.0, "USD"), (None, None)),
    ],
)
def test_decide_coincide_con_la_clasificacion(a, b, expected):
    summary = _summary(a=a, b=b)
    assert decide(summary) == expected
    winner, _ = expected
    leaders = [side for position, side in rank_sides(summary) if position == 1]
    assert leaders == ([winner] if winner else ["a", "b"])


def _results(a, b, runs=1):
    """Dos tareas de 4 tests; ``a`` y ``b`` son los tests superados en cada una."""
    data = copy.deepcopy(RESULTS)
    data["runs"] = runs
    data["tasks"] = [
        {
            **data["tasks"][0],
            "id": f"t{i}",
            "results": {
                side: [_attempt(passed[i], 4, cost=None) for _ in range(runs)]
                for side, passed in (("a", a), ("b", b))
            },
        }
        for i in range(2)
    ]
    return data


def _verdict(html):
    text = re.search(r'<p class="verdict">(.*?)</p>', html, flags=re.S).group(1)
    return re.sub(r"<[^>]+>", "", text)


def test_el_veredicto_indica_que_gana_por_tareas_aunque_tenga_menos_tests():
    # A: 4 + 0 = 4 tests y 1 tarea; B: 3 + 3 = 6 tests y 0 tareas. Antes decía «gana B por 2».
    text = _verdict(render_report(_results(a=(4, 0), b=(3, 3))))
    assert text == "gana A por tareas resueltas (1 frente a 0)"


def test_el_veredicto_indica_que_decide_por_tests():
    text = _verdict(render_report(_results(a=(4, 2), b=(4, 1))))
    assert text == "gana A por tests superados (6 frente a 5, con las mismas tareas resueltas)"


def test_el_veredicto_con_varias_ejecuciones_menciona_la_suma():
    text = _verdict(render_report(_results(a=(4, 2), b=(4, 1), runs=3)))
    assert text.endswith("(suma de 3 ejecuciones)")


def test_el_veredicto_indica_que_decide_por_coste():
    data = _results(a=(4, 2), b=(4, 2))
    for task in data["tasks"]:
        task["results"]["a"][0]["cost"] = 0.5
        task["results"]["b"][0]["cost"] = 0.25
    data["contenders"]["a"]["price"] = data["contenders"]["b"]["price"] = {"currency": "EUR"}
    text = _verdict(render_report(data))
    assert text == (
        "gana B por coste (0,5000 EUR frente a 1,00 EUR, con las mismas tareas resueltas y tests)"
    )


def test_el_veredicto_de_un_empate_dice_en_que_empatan():
    text = _verdict(render_report(_results(a=(4, 2), b=(4, 2))))
    assert text == "empate en tareas resueltas y tests (sin coste comparable)"
