"""Enfrentamientos directos (v1.2.0): cálculo de la matriz, grafo SVG, panel, tabla y CSP."""

from __future__ import annotations

import copy
import json
import re
from html.parser import HTMLParser

import pytest

from modelduel.leaderboard import aggregate as aggregate_models
from modelduel.leaderboard import build_leaderboard, head_to_head_models, load_duels, rank_models
from modelduel.report import render_report
from modelduel.report.h2h import (
    MAX_GRAPH_NODES,
    HeadToHead,
    Node,
    Pair,
    aggregate_head_to_head,
    clip,
    h2h_css,
    head_to_head,
    pair_sentence,
    render_h2h,
    task_score,
)
from tests.conftest import ROOT
from tests.test_csp import _assert_report_csp

DUEL = ROOT / "results" / "2026-10-01-duelo-alfa-beta.json"
DUEL_X2 = ROOT / "results" / "2026-10-01-duelo-gamma-alfa-x2.json"
LEAGUE = ROOT / "results" / "2026-10-01-liga-alfa-beta-gamma.json"
HOSTILE = "</style><script>alert(1)</script>\"'><svg onload=x>"


def attempt(solved: bool, passed: int, total: int = 8) -> dict:
    return {"solved": solved, "passed": passed, "total": total}


def make_results(tasks: list[tuple[str, dict[str, list[dict]]]], n: int = 2, runs: int = 1):
    sides = "abcdef"[:n]
    return {
        "runs": runs,
        "contenders": {side: {"spec": f"replay:m{side}"} for side in sides},
        "tasks": [{"title": title, "results": by_side} for title, by_side in tasks],
    }


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def two(pair: Pair) -> HeadToHead:
    return HeadToHead(
        [Node("a", "a", "a", "A", "a"), Node("b", "b", "b", "B", "b")], {(0, 1): pair}
    )


def synthetic(n: int, played: bool = True) -> HeadToHead:
    """``n`` nodos (más de los 6 que admite results.json), con el primero ganándolos todos."""
    nodes = [Node(f"k{i}", f"modelo-{i}", f"prov:modelo-{i}", str(i + 1), "n") for i in range(n)]
    pairs = {}
    for i in range(n):
        for j in range(i + 1, n):
            pair = Pair(i, j)
            if played:
                pair.add("t", [attempt(i == 0, 8 if i == 0 else 3)], [attempt(False, 3)], 1)
            pairs[(i, j)] = pair
    return HeadToHead(nodes, pairs)


# ---------------------------------------------------------------- cálculo


def test_task_score_resolver_pesa_mas_que_los_tests_y_sin_intentos_es_none():
    assert task_score([], 1) is None
    assert task_score([attempt(True, 8)], 1) == (1, 8)
    assert task_score([attempt(False, 7)], 1) == (0, 7)
    # Con --runs 2 solo está resuelta si lo está en las dos ejecuciones (y las tiene todas).
    assert task_score([attempt(True, 8), attempt(False, 6)], 2) == (0, 14)
    assert task_score([attempt(True, 8)], 2) == (0, 8)
    assert task_score([attempt(True, 8), attempt(True, 8)], 2) == (1, 16)


def test_victoria_derrota_empate_y_tareas_sin_datos():
    data = make_results(
        [
            ("gana A", {"a": [attempt(True, 8)], "b": [attempt(False, 7)]}),
            ("gana B por tests", {"a": [attempt(False, 2)], "b": [attempt(False, 5)]}),
            ("empate", {"a": [attempt(True, 8)], "b": [attempt(True, 8)]}),
            ("gana A otra", {"a": [attempt(False, 4)], "b": [attempt(False, 3)]}),
            ("sin B", {"a": [attempt(True, 8)]}),
        ]
    )
    h2h = head_to_head(data)
    pair = h2h.pair(0, 1)
    assert (pair.wins_i, pair.wins_j, pair.ties, pair.unknown, pair.played) == (2, 1, 1, 1, 4)
    assert pair.leader == 0
    assert [m.winner for m in pair.meetings] == ["i", "j", None, "i"]
    assert (pair.meetings[1].passed_i, pair.meetings[1].passed_j) == (2, 5)
    assert h2h.versus(0, 1) == (2, 1, 1) and h2h.versus(1, 0) == (1, 2, 1)
    assert h2h.record(0) == (2, 1, 1) and h2h.record(1) == (1, 2, 1)
    assert pair_sentence(h2h, pair) == "A ma contra B mb: gana A ma, 2 tareas a 1, 1 empate"
    assert "1 tarea sin datos de alguno" in render_h2h(h2h, intro="")


def test_runs_suma_tests_y_exige_todas_las_ejecuciones():
    data = make_results(
        [
            # A resuelve una de dos ejecuciones (13 tests); B no resuelve ninguna pero suma 14.
            ("x", {"a": [attempt(True, 8), attempt(False, 5)], "b": [attempt(False, 7)] * 2}),
            # B solo tiene una de las dos ejecuciones: no cuenta como resuelta.
            ("y", {"a": [attempt(True, 8), attempt(True, 8)], "b": [attempt(True, 8)]}),
        ],
        runs=2,
    )
    pair = head_to_head(data).pair(0, 1)
    assert [m.winner for m in pair.meetings] == ["j", "i"]
    assert pair.leader is None and score_text(pair) == "1–1"


def score_text(pair: Pair) -> str:
    match = re.search(r'class="score"[^>]*>([^<]+)<', render_h2h(two(pair), intro=""))
    assert match
    return match.group(1)


def test_el_marcador_pone_delante_al_que_gana_mas():
    pair = Pair(0, 1, wins_i=1, wins_j=3)
    assert pair.leader == 1 and score_text(pair) == "3–1"
    assert Pair(0, 1).leader is None and Pair(0, 1).played == 0


def test_tres_lados_simetria_record_y_versus():
    data = make_results(
        [
            ("t1", {"a": [attempt(True, 8)], "b": [attempt(False, 1)], "c": [attempt(False, 2)]}),
            ("t2", {"a": [attempt(True, 8)], "b": [attempt(True, 8)], "c": [attempt(False, 0)]}),
        ],
        n=3,
    )
    h2h = head_to_head(data)
    assert h2h.pair(2, 0) is h2h.pair(0, 2)
    assert h2h.versus(0, 1) == (1, 0, 1)
    assert h2h.versus(0, 2) == (2, 0, 0)
    assert h2h.versus(2, 1) == (1, 1, 0)
    assert h2h.record(0) == (3, 0, 1)
    assert h2h.record(1) == (1, 2, 1)
    assert h2h.record(2) == (1, 3, 0)
    # Cada tarea ganada por uno es una perdida por otro.
    assert sum(h2h.record(k)[0] for k in range(3)) == sum(h2h.record(k)[1] for k in range(3))


def test_los_results_del_repositorio():
    # Calculado a mano leyendo los JSON (slug, intervalos y duración).
    assert head_to_head(load(DUEL)).versus(0, 1) == (1, 1, 1)
    assert head_to_head(load(DUEL_X2)).versus(0, 1) == (1, 1, 1)  # gamma-alfa, 2 ejecuciones
    league = head_to_head(load(LEAGUE))
    assert [node.badge for node in league.nodes] == ["A", "B", "C"]
    assert league.versus(0, 1) == (1, 1, 1)  # alfa-beta
    assert league.versus(0, 2) == (1, 1, 1)  # alfa-gamma
    assert league.versus(1, 2) == (1, 1, 1)  # beta-gamma


def test_agregado_de_la_clasificacion():
    duels = load_duels(ROOT / "results")
    ranking = rank_models(aggregate_models(duels))
    h2h = head_to_head_models(duels, ranking)
    keys = [node.key for node in h2h.nodes]
    assert keys == [model["spec"] for _p, model in ranking]
    assert [node.badge for node in h2h.nodes] == [str(p) for p, _m in ranking]
    assert all(node.css == "n" for node in h2h.nodes)
    alfa, beta, gamma = (keys.index(f"replay:{m}") for m in ("alfa", "beta", "gamma"))
    assert h2h.versus(alfa, beta) == (2, 2, 2)  # duelo + liga
    assert h2h.versus(alfa, gamma) == (2, 2, 2)  # duelo x2 + liga
    assert h2h.versus(beta, gamma) == (1, 1, 1)  # solo la liga
    titles = [m.title for m in h2h.pair(alfa, gamma).meetings]
    assert "2026-10-01-duelo-gamma-alfa-x2 · Fusionar intervalos" in titles


def test_agregado_ignora_el_mismo_spec_en_los_dos_lados_y_usa_nombres_completos_si_chocan():
    twin = make_results([("t", {"a": [attempt(True, 8)], "b": [attempt(False, 1)]})])
    twin["contenders"] = {"a": {"spec": "replay:x"}, "b": {"spec": "replay:x"}}
    other = make_results([("t", {"a": [attempt(True, 8)], "b": [attempt(False, 1)]})])
    other["contenders"] = {"a": {"spec": "replay:x"}, "b": {"spec": "openai:x"}}
    h2h = aggregate_head_to_head(
        [("gemelos", twin), ("otro", other)], ["replay:x", "openai:x"], ["1", "2"]
    )
    assert h2h.versus(0, 1) == (1, 0, 0)
    # Repetido en una liga con un tercero: la pareja x-y cuenta una sola vez (revisión cruzada).
    trio = make_results(
        [("t", {"a": [attempt(True, 8)], "b": [attempt(True, 8)], "c": [attempt(False, 1)]})],
        n=3,
    )
    trio["contenders"] = {"a": {"spec": "p:x"}, "b": {"spec": "p:x"}, "c": {"spec": "p:y"}}
    assert aggregate_head_to_head([("l", trio)], ["p:x", "p:y"], ["1", "2"]).versus(0, 1) == (
        1,
        0,
        0,
    )
    assert [node.label for node in h2h.nodes] == ["replay:x", "openai:x"]
    # Nodos en otro orden que los lados del duelo: el balance sigue siendo el de cada modelo.
    flipped = aggregate_head_to_head([("otro", other)], ["openai:x", "replay:x"], ["1", "2"])
    assert flipped.versus(1, 0) == (1, 0, 0)


# ---------------------------------------------------------------- HTML


class _Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[tuple[str, dict[str, str | None]]] = []

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def tags(html: str) -> list[tuple[str, dict[str, str | None]]]:
    parser = _Tags()
    parser.feed(html)
    return parser.tags


def handlers(html: str) -> list[str]:
    """Atributos de evento (``on…``) en cualquier etiqueta: no puede haber ninguno."""
    return [name for _t, attrs in tags(html) for name in attrs if name.startswith("on")]


def with_class(html: str, name: str) -> list[dict[str, str | None]]:
    return [a for _t, a in tags(html) if name in (a.get("class") or "").split()]


@pytest.mark.parametrize("n", [2, 3, 6, 8])
def test_grafo_con_n_nodos_focusables_y_etiquetados(n):
    html = render_h2h(synthetic(n), intro="intro")
    assert html.count('<svg class="h2h-graph') == 1
    nodes, edges = with_class(html, "h2h-node"), with_class(html, "h2h-edge")
    assert len(nodes) == n and len(edges) == n * (n - 1) // 2
    for element in nodes + edges:
        assert element["tabindex"] == "0" and element["role"] == "img" and element["aria-label"]
    assert len(with_class(html, "h2h-info")) == 1 + n + n * (n - 1) // 2  # pista, nodos, parejas
    assert with_class(html, "h2h-panel")[0]["aria-hidden"] == "true"
    assert bool(with_class(html, "dense")) == (n >= 4)
    assert "h2h-legend" in html
    # Tabla: n filas, una columna por modelo más «Modelo» y «Balance», y la diagonal.
    table = html[html.index('<table class="h2h-matrix"') :]
    assert table.count('<th scope="row"') == n
    assert table.count('<th scope="col"') == n + 2
    assert table.count('class="self"') == n
    # Nada se sale del viewBox: los nodos y sus textos quedan dentro.
    box = re.search(r'<svg class="h2h-graph[^"]*" viewBox="0 0 (\d+) (\d+)"', html)
    assert box
    width, height = map(float, box.groups())
    for x, y in re.findall(r'<text class="(?:name|rec)" x="([\d.]+)" y="([\d.]+)"', html):
        assert 0 < float(x) < width and 14 < float(y) < height


def test_la_flecha_apunta_al_que_pierde():
    def tip_x(pair: Pair) -> float:
        match = re.search(r'class="tip" points="([\d.]+),', render_h2h(two(pair), intro=""))
        assert match
        return float(match.group(1))

    assert tip_x(Pair(0, 1, wins_i=1)) > 280  # gana A: punta junto a B (derecha)
    assert tip_x(Pair(0, 1, wins_j=1)) < 280
    html = render_h2h(two(Pair(0, 1, ties=2)), intro="")
    assert 'class="tip"' not in html and "h2h-edge h2h-p0-1 x0 x1 tie" in html
    assert "2 empates" in html


def test_sin_enfrentamientos_no_hay_arista_y_la_tabla_lo_dice():
    html = render_h2h(synthetic(3, played=False), intro="")
    assert not with_class(html, "h2h-edge")
    assert html.count("sin enfrentamientos</span>") == 6


def test_mas_de_ocho_modelos_solo_tabla():
    html = render_h2h(synthetic(MAX_GRAPH_NODES + 1), intro="")
    assert "h2h-graph" not in html and "h2h-panel" not in html and "h2h-many" in html
    assert html.count('<th scope="row"') == MAX_GRAPH_NODES + 1
    assert h2h_css(MAX_GRAPH_NODES + 1) == "" and h2h_css(1) == ""


def test_h2h_css_solo_depende_de_n():
    css = h2h_css(8)
    assert css == h2h_css(8) and css != h2h_css(7)
    assert ".h2h-info-n7{display:block}" in css and ".h2h-info-p6-7{display:block}" in css
    assert "<" not in css and "opacity" not in css
    assert re.fullmatch(r"[A-Za-zÁÉÍÓÚáéíóú0-9 .:(),{}\-#;/*\n]+", css)


def test_el_panel_recorta_las_tareas_largas():
    pair = Pair(0, 1)
    for k in range(15):
        pair.add(f"t{k}", [attempt(True, 8)], [attempt(False, 1)], 1)
    html = render_h2h(two(pair), intro="")
    assert "t11</span>" in html and "t12</span>" not in html and "… y 3 tareas más" in html


def test_clip_recorta_por_caracteres():
    assert clip("corto", 16) == "corto"
    assert clip("x" * 20, 16) == "x" * 15 + "…"
    assert clip("x" * 14 + "😀" + "yy", 16) == "x" * 14 + "😀…"


def test_datos_hostiles_salen_escapados():
    data = make_results([(HOSTILE, {"a": [attempt(True, 8)], "b": [attempt(False, 1)]})])
    data["contenders"]["a"]["spec"] = "x:" + HOSTILE
    html = render_h2h(head_to_head(data), intro=HOSTILE)
    assert "<script" not in html and "<svg onload" not in html and "</style>" not in html
    assert not handlers(html)
    assert "style=" not in html
    assert "&lt;/style&gt;&lt;script&gt;" in html
    # También en aria-label: las comillas van escapadas y no se puede cerrar el atributo.
    labels = [a["aria-label"] or "" for _t, a in tags(html) if a.get("aria-label")]
    assert any(HOSTILE in label for label in labels)


# ---------------------------------------------------------------- integración


@pytest.mark.parametrize("path", [DUEL, DUEL_X2, LEAGUE], ids=["duelo", "duelo-x2", "liga"])
def test_los_informes_traen_la_seccion_y_siguen_con_la_csp(path):
    html = render_report(load(path))
    assert '<h2 id="h2h-titulo">Enfrentamientos directos</h2>' in html
    assert '<section class="h2h" aria-labelledby="h2h-titulo">' in html
    n = len(load(path)["contenders"])
    assert len(with_class(html, "h2h-node")) == n
    assert f".h2h-info-n{n - 1}{{display:block}}" in html and f".h2h-info-n{n}{{" not in html
    _assert_report_csp(html)


def test_un_informe_hostil_conserva_la_csp_y_no_inyecta():
    evil = copy.deepcopy(load(LEAGUE))
    evil["tasks"][0]["title"] = HOSTILE
    for side in evil["contenders"].values():
        side["spec"] = "x:" + HOSTILE
    html = render_report(evil)
    _assert_report_csp(html)
    section = html[html.index('<section class="h2h"') : html.index("Matriz por tarea")]
    assert "<script" not in section and not handlers(section)


def test_la_clasificacion_trae_la_seccion(tmp_path):
    index = build_leaderboard(ROOT / "results", tmp_path / "lb")
    html = index.read_text(encoding="utf-8")
    assert html.index("Enfrentamientos directos") < html.index("Histórico de duelos")
    assert len(with_class(html, "h2h-node")) == 3
    _assert_report_csp(html)
