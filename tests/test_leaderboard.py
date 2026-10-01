"""Clasificación pública: agregado de ``results/*.json``, histórico y página estática."""

import json
import re
from html.parser import HTMLParser

import pytest

from modelduel.leaderboard import (
    aggregate,
    build_leaderboard,
    load_duels,
    rank_models,
    render_leaderboard,
)
from modelduel.results import ResultsError
from tests.conftest import ROOT


def _attempt(solved: bool, cost: float | None) -> dict:
    passed, total = (4, 4) if solved else (1, 4)
    return {
        "status": "ok",
        "passed": passed,
        "failed": total - passed,
        "errors": 0,
        "skipped": 0,
        "total": total,
        "solved": solved,
        "duration_s": 0.1,
        "output": "",
        "message": "",
        "latency_s": 1.0,
        "input_tokens": 10,
        "output_tokens": 10,
        "cost": cost,
        "code": "x = 1\n",
        "response": "",
        "run": 1,
    }


def make_results(created: str, sides: dict, n_tasks: int = 3, version: str = "0.4.0") -> dict:
    """``sides``: letra -> (spec, tareas resueltas, coste por intento o None, moneda)."""
    contenders = {}
    for side, (spec, _solved, cost, currency) in sides.items():
        price = {"currency": currency, "fictitious": False} if cost is not None else None
        contenders[side] = {"spec": spec, "price": price}
    tasks = [
        {
            "id": f"t{i}",
            "title": f"Tarea {i}",
            "difficulty": None,
            "statement": "x",
            "tests_expected": 4,
            "results": {
                side: [_attempt(i < solved, cost)] for side, (_s, solved, cost, _c) in sides.items()
            },
        }
        for i in range(n_tasks)
    ]
    return {
        "schema": 1,
        "version": version,
        "created_at": created,
        "status": "complete",
        "runs": 1,
        "timeout_s": 20,
        "contenders": contenders,
        "tasks": tasks,
    }


def write(folder, name: str, results: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{name}.json").write_text(json.dumps(results), encoding="utf-8")


@pytest.fixture
def folder(tmp_path):
    base = tmp_path / "results"
    write(
        base,
        "2026-01-01-uno",
        make_results(
            "2026-01-01T10:00:00+00:00",
            {"a": ("x:fuerte", 3, 0.01, "USD"), "b": ("x:flojo", 1, 0.02, "USD")},
        ),
    )
    write(
        base,
        "2026-02-01-dos",
        make_results(
            "2026-02-01T10:00:00+00:00",
            {
                "a": ("x:fuerte", 2, 0.01, "USD"),
                "b": ("x:medio", 2, 0.01, "USD"),
                "c": ("x:flojo", 0, 0.02, "USD"),
            },
            n_tasks=2,
            version="0.3.0",
        ),
    )
    return base


def test_carga_los_duelos_por_fecha_con_su_id(folder):
    duels = load_duels(folder)
    assert [d.id for d in duels] == ["2026-01-01-uno", "2026-02-01-dos"]
    assert duels[1].results["version"] == "0.3.0"


def test_agregado_suma_duelos_tareas_y_tests(folder):
    models = aggregate(load_duels(folder))
    fuerte = models["x:fuerte"]
    assert fuerte["duels"] == 2
    assert (fuerte["tasks_solved"], fuerte["tasks_total"]) == (5, 5)
    assert (fuerte["tests_passed"], fuerte["tests_total"]) == (20, 20)
    assert fuerte["cost"] == pytest.approx(0.05)
    assert fuerte["currency"] == "USD"
    assert models["x:medio"]["duels"] == 1


def test_clasificacion_por_tasas(folder):
    # fuerte 5/5 y medio 2/2 empatan al 100 % con el mismo coste por tarea; flojo resuelve 1/5.
    ranking = rank_models(aggregate(load_duels(folder)))
    assert [(p, r["spec"]) for p, r in ranking] == [(1, "x:fuerte"), (1, "x:medio"), (3, "x:flojo")]


def test_un_modelo_con_mas_duelos_no_gana_por_volumen(tmp_path):
    base = tmp_path / "r"
    write(
        base,
        "d1",
        make_results(
            "2026-01-01T10:00:00+00:00",
            {"a": ("x:mucho", 2, None, None), "b": ("x:poco", 3, None, None)},
        ),
    )
    write(
        base,
        "d2",
        make_results(
            "2026-01-02T10:00:00+00:00",
            {"a": ("x:mucho", 2, None, None), "b": ("x:otro", 0, None, None)},
        ),
    )
    ranking = rank_models(aggregate(load_duels(base)))
    # mucho: 4/6 tareas (acumula más que poco: 4 > 3) pero poco tiene tasa 3/3.
    assert [(p, r["spec"]) for p, r in ranking] == [(1, "x:poco"), (2, "x:mucho"), (3, "x:otro")]


def test_empates_comparten_posicion_y_el_coste_desempata(tmp_path):
    base = tmp_path / "r"
    write(
        base,
        "d",
        make_results(
            "2026-01-01T10:00:00+00:00",
            {"a": ("x:caro", 2, 0.5, "USD"), "b": ("x:barato", 2, 0.1, "USD")},
        ),
    )
    ranking = rank_models(aggregate(load_duels(base)))
    assert [(p, r["spec"]) for p, r in ranking] == [(1, "x:barato"), (2, "x:caro")]
    base2 = tmp_path / "r2"
    write(
        base2,
        "d",
        make_results(
            "2026-01-01T10:00:00+00:00", {"a": ("x:a", 2, 0.1, "USD"), "b": ("x:b", 2, 0.1, "USD")}
        ),
    )
    ranking = rank_models(aggregate(load_duels(base2)))
    assert [p for p, _r in ranking] == [1, 1]


def test_coste_sin_datos_si_falta_precio_o_hay_monedas_distintas(tmp_path):
    base = tmp_path / "r"
    write(
        base,
        "d1",
        make_results(
            "2026-01-01T10:00:00+00:00", {"a": ("x:a", 3, 0.1, "USD"), "b": ("x:b", 3, None, None)}
        ),
    )
    write(
        base,
        "d2",
        make_results(
            "2026-01-02T10:00:00+00:00", {"a": ("x:a", 3, 0.1, "EUR"), "b": ("x:c", 3, 0.1, "EUR")}
        ),
    )
    models = aggregate(load_duels(base))
    assert models["x:a"]["cost"] is None  # USD y EUR no se suman
    assert models["x:b"]["cost"] is None  # sin precio en uno de sus duelos
    assert models["x:c"]["cost"] == pytest.approx(0.3)


@pytest.mark.parametrize("bad", ["vacia", "no-existe"])
def test_carpeta_vacia_o_inexistente(tmp_path, bad):
    (tmp_path / "vacia").mkdir()
    with pytest.raises(ResultsError, match="No hay resultados"):
        load_duels(tmp_path / bad)


def test_json_ilegible_y_duelo_incompleto_son_errores(tmp_path):
    base = tmp_path / "r"
    base.mkdir()
    (base / "roto.json").write_text("{no es json", encoding="utf-8")
    with pytest.raises(ResultsError, match="roto.json"):
        load_duels(base)
    (base / "roto.json").unlink()
    sides = {"a": ("x:a", 1, 0.1, "USD"), "b": ("x:b", 1, 0.1, "USD")}
    incomplete = make_results("2026-01-01T10:00:00+00:00", sides)
    incomplete["status"] = "in_progress"
    write(base, "parcial", incomplete)
    with pytest.raises(ResultsError, match="incompleto"):
        load_duels(base)


def test_la_pagina_muestra_clasificacion_historico_y_enlaces(folder):
    html = render_leaderboard(load_duels(folder))
    assert "Clasificación" in html and "Histórico" in html
    assert 'href="duelos/2026-01-01-uno/index.html"' in html
    assert 'href="duelos/2026-02-01-dos/index.html"' in html
    assert "x:fuerte" in html
    assert "<script" not in html.lower()
    assert '<html lang="es">' in html
    # el más reciente primero en el histórico
    assert html.index("2026-02-01-dos") < html.index("2026-01-01-uno")


def test_la_pagina_escapa_el_contenido_de_los_resultados(tmp_path):
    base = tmp_path / "r"
    evil = make_results(
        "2026-01-01T10:00:00+00:00",
        {"a": ("x:<img src=x onerror=alert(1)>", 3, 0.1, "USD"), "b": ("x:b", 1, 0.1, "USD")},
    )
    evil["version"] = "<script>1</script>"
    write(base, "d", evil)
    html = render_leaderboard(load_duels(base))
    assert "<img src=x" not in html
    assert "<script" not in html.lower()


def test_build_escribe_pagina_e_informes(folder, tmp_path):
    out = tmp_path / "salida"
    index = build_leaderboard(folder, out)
    assert index == out / "index.html"
    assert index.read_text(encoding="utf-8").startswith("<!doctype")
    for duel_id in ("2026-01-01-uno", "2026-02-01-dos"):
        report = (out / "duelos" / duel_id / "index.html").read_text(encoding="utf-8")
        assert "modelduel" in report


def test_los_resultados_sembrados_del_repo_son_validos():
    duels = load_duels(ROOT / "results")
    assert len(duels) >= 2
    assert all(d.results["status"] == "complete" for d in duels)
    assert {"replay:alfa", "replay:beta", "replay:gamma"} <= set(aggregate(duels))


def _luminance(color: str) -> float:
    channels = [int(color.lstrip("#")[i : i + 2], 16) / 255 for i in (0, 2, 4)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def _contrast(fg: str, bg: str) -> float:
    hi, lo = sorted((_luminance(fg), _luminance(bg)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _vars(block: str) -> dict[str, str]:
    found = re.findall(r"--([\w-]+):\s*#([0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b", block)
    return {n: "#" + (v if len(v) == 6 else "".join(c * 2 for c in v)) for n, v in found}


def test_contraste_aa_de_la_pagina_en_pantalla_e_impresion(folder):
    html = render_leaderboard(load_duels(folder))
    screen = _vars(html.split(":root {")[1].split("}")[0])
    printed = _vars(html.split("@media print")[1].split("}")[0])
    for bg in ("bg", "panel"):
        for fg in ("a", "text", "muted"):
            assert _contrast(screen[fg], screen[bg]) >= 4.5, (fg, bg)
    for fg in ("a", "text", "muted"):
        assert _contrast(printed[fg], "#ffffff") >= 4.5, fg
    # La barra es el único color de datos: lima sobre la pista, con al menos 3:1 (WCAG 1.4.11).
    assert _contrast(screen["a"], screen["bg"]) >= 3


def test_la_pagina_es_accesible_y_legible_en_movil_e_impresion(folder):
    html = render_leaderboard(load_duels(folder))
    assert 'name="viewport"' in html and "<title>" in html
    assert 'class="skip"' in html and 'id="contenido"' in html
    assert html.count("<svg") == html.count("<title>") - 1  # el <title> de la página + uno por SVG
    assert html.count('role="img"') == html.count("<svg")
    assert 'scope="row"' in html and 'role="region"' in html
    assert "@media (max-width: 720px)" in html and "@media print" in html


PAYLOADS = ("<script>alert(1)</script>", "<img src=x onerror=alert(2)>")


def _evil(sides: dict, currency: str, n_tasks: int = 2) -> dict:
    """Resultados de un tercero con HTML en todos los campos de texto que llegan a un informe."""
    results = make_results("2026-03-01T10:00:00+00:00", sides, n_tasks=n_tasks)
    results["version"] = PAYLOADS[0]
    results["created_at"] = "2026-03-01T10:00:00+00:00"
    for side in sides:
        results["contenders"][side]["price"] = {"currency": currency, "fictitious": False}
    for task in results["tasks"]:
        task["title"] = PAYLOADS[0]
        task["difficulty"] = PAYLOADS[1]
        task["statement"] = PAYLOADS[1]
        for attempts in task["results"].values():
            for attempt in attempts:
                attempt["message"] = PAYLOADS[0]
                attempt["code"] = PAYLOADS[1]
                attempt["output"] = PAYLOADS[0]
                attempt["response"] = PAYLOADS[1]
    return results


class _Tags(HTMLParser):
    """Etiquetas y atributos que un navegador vería de verdad (el texto escapado no cuenta)."""

    def __init__(self):
        super().__init__()
        self.found: list[str] = []

    def handle_starttag(self, tag, attrs):
        self.found.append(tag)
        self.found.extend(name for name, _value in attrs)


def _assert_nothing_unescaped(out):
    files = [f for f in out.rglob("*") if f.is_file()]
    assert files
    for file in files:
        text = file.read_text(encoding="utf-8")
        for needle in ("<script>alert", "<img src=x"):
            assert needle not in text, f"{needle} sin escapar en {file}"
        parser = _Tags()
        parser.feed(text)
        assert not {"script", "img", "onerror"} & set(parser.found), f"HTML inyectado en {file}"


def test_json_malicioso_no_inyecta_html_en_ningun_archivo_generado(tmp_path):
    base = tmp_path / "r"
    # Duelo de dos que se decide por coste: la moneda entra en el texto del veredicto.
    duel = _evil(
        {"a": (PAYLOADS[0], 3, 0.1, "USD"), "b": (PAYLOADS[1], 3, 0.5, "USD")}, PAYLOADS[1]
    )
    league = _evil(
        {
            "a": (PAYLOADS[0], 3, 0.1, "USD"),
            "b": (PAYLOADS[1], 2, 0.2, "USD"),
            "c": ("x:c", 1, 0.3, "USD"),
        },
        PAYLOADS[0],
    )
    write(base, "duelo-a'b&c", duel)  # <, > y " no valen en nombres de archivo de Windows
    write(base, "liga", league)
    out = tmp_path / "salida"
    build_leaderboard(base, out)
    _assert_nothing_unescaped(out)


def test_failed_no_numerico_da_un_error_limpio_y_no_publica_nada(tmp_path):
    base = tmp_path / "r"
    results = make_results(
        "2026-03-01T10:00:00+00:00", {"a": ("x:a", 1, 0.1, "USD"), "b": ("x:b", 2, 0.1, "USD")}
    )
    results["tasks"][0]["results"]["a"][0]["failed"] = PAYLOADS[1]
    write(base, "d", results)
    out = tmp_path / "salida"
    with pytest.raises(ResultsError, match="no parece de modelduel"):
        build_leaderboard(base, out)
    assert not (out / "index.html").exists()


def test_el_coste_por_tarea_se_divide_entre_los_intentos_totales():
    # Con --runs 2 el coste suma el doble de intentos: 0,6 en 6 intentos (0,1 cada uno) es más
    # barato que 0,4 en 3 (0,133 cada uno), aunque por tarea resuelta parezca lo contrario.
    def model(spec, cost, attempts):
        return {
            "spec": spec,
            "duels": 1,
            "tasks_solved": 3,
            "tasks_total": 3,
            "tests_passed": 12,
            "tests_total": 12,
            "attempts_total": attempts,
            "cost": cost,
            "currency": "USD",
            "fictitious": False,
        }

    models = {"x:doble": model("x:doble", 0.6, 6), "x:simple": model("x:simple", 0.4, 3)}
    assert [r["spec"] for _p, r in rank_models(models)] == ["x:doble", "x:simple"]


def test_el_agregado_cuenta_los_intentos_de_todas_las_ejecuciones():
    duels = load_duels(ROOT / "results")
    assert (
        aggregate(duels)["replay:gamma"]["attempts_total"] == 3 + 6
    )  # la liga y el duelo con --runs 2
