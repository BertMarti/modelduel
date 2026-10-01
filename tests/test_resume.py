"""Guardado incremental atómico y reanudación de un duelo (sin red)."""

from __future__ import annotations

import json
import os

import pytest

from modelduel.cli import main
from modelduel.duel import run_duel
from modelduel.pricing import Price
from modelduel.providers import ProviderError, Response, get_provider
from modelduel.report import render_report
from modelduel.results import load_results, save_results
from modelduel.resume import ResumeError, plan_resume, task_fingerprint
from tests.conftest import ADD_TESTS

CORRECT = "```python\ndef add(a, b):\n    return a + b\n```"
WRONG = "```python\ndef add(a, b):\n    return 0\n```"


class Provider:
    """Responde con ``answer``; si se le indica, se corta con Ctrl+C en la llamada ``cut_at``."""

    def __init__(self, spec, answer=CORRECT, cut_at=None):
        self.spec = spec
        self.answer = answer
        self.cut_at = cut_at
        self.calls = 0

    def complete(self, prompt, *, task_id=None):
        self.calls += 1
        if self.cut_at is not None and self.calls == self.cut_at:
            raise KeyboardInterrupt
        if isinstance(self.answer, Exception):
            raise self.answer
        return Response(text=self.answer, input_tokens=100, output_tokens=50, latency_s=0.5)


def _providers(**kwargs):
    return {"a": Provider("fake:a", **kwargs.get("a", {})), "b": Provider("fake:b")}


# ---------------------------------------------------------------- escritura atómica


def test_save_results_atomico_no_deja_temporales(tmp_path):
    path = tmp_path / "out" / "results.json"
    save_results({"tasks": [], "contenders": {}}, path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"tasks": [], "contenders": {}}
    assert [p.name for p in path.parent.iterdir()] == ["results.json"]


def test_save_results_fallido_conserva_la_version_anterior(tmp_path, monkeypatch):
    path = tmp_path / "results.json"
    save_results({"version": "buena"}, path)

    def boom(*_args):
        raise OSError("disco lleno")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError, match="disco lleno"):
        save_results({"version": "rota"}, path)
    assert json.loads(path.read_text(encoding="utf-8")) == {"version": "buena"}
    assert [p.name for p in tmp_path.iterdir()] == ["results.json"]  # sin .tmp


def test_save_results_reintenta_si_windows_tiene_el_archivo_abierto(tmp_path, monkeypatch):
    real = os.replace
    fallos = []

    def flaky(src, dst):
        if len(fallos) < 2:
            fallos.append(1)
            raise PermissionError("en uso")
        real(src, dst)

    monkeypatch.setattr(os, "replace", flaky)
    save_results({"x": 1}, tmp_path / "results.json")
    assert len(fallos) == 2
    assert (tmp_path / "results.json").is_file()


def test_save_results_se_rinde_tras_varios_permisos_denegados(tmp_path, monkeypatch):
    def denied(*_args):
        raise PermissionError("en uso")

    monkeypatch.setattr(os, "replace", denied)
    with pytest.raises(PermissionError):
        save_results({"x": 1}, tmp_path / "results.json")


# ---------------------------------------------------------------- guardado incremental


def test_on_update_se_llama_tras_cada_intento_y_el_estado_pasa_a_completo(make_task):
    task = make_task(ADD_TESTS)
    snapshots = []
    run_duel(
        [task],
        _providers(),
        {},
        runs=2,
        on_update=lambda r: snapshots.append(
            (r["status"], sum(len(v) for v in r["tasks"][0]["results"].values()))
        ),
    )
    # inicial + 4 intentos + cierre
    assert snapshots == [
        ("in_progress", 0),
        ("in_progress", 1),
        ("in_progress", 2),
        ("in_progress", 3),
        ("in_progress", 4),
        ("complete", 4),
    ]


def test_corte_a_mitad_deja_un_results_json_valido_y_parcial(make_task, tmp_path):
    task = make_task(ADD_TESTS)
    path = tmp_path / "results.json"
    with pytest.raises(KeyboardInterrupt):
        run_duel(
            [task],
            _providers(a={"cut_at": 2}),
            {},
            runs=2,
            on_update=lambda r: save_results(r, path),
        )
    partial = load_results(path)  # se puede leer y resumir
    assert partial["status"] == "in_progress"
    lens = {s: len(partial["tasks"][0]["results"][s]) for s in ("a", "b")}
    assert lens == {"a": 1, "b": 1}  # A y B en la ronda 1; A en la ronda 2 se cortó
    assert partial["summary"]["a"]["tasks_solved"] == 0  # faltan ejecuciones: aún no cuenta
    html = render_report(partial)
    assert "Duelo incompleto: 2 de 4 intentos" in html and "--resume" in html


def test_corte_y_reanudacion_solo_repite_lo_que_falta(make_task, tmp_path):
    task = make_task(ADD_TESTS)
    path = tmp_path / "results.json"
    with pytest.raises(KeyboardInterrupt):
        run_duel(
            [task],
            _providers(a={"cut_at": 2}),
            {},
            runs=2,
            on_update=lambda r: save_results(r, path),
        )
    previous = load_results(path)
    providers = _providers()
    specs = {s: p.spec for s, p in providers.items()}
    reuse, warnings = plan_resume(previous, [task], specs, 2, previous["timeout_s"])
    assert warnings == [] and len(reuse) == 2
    results = run_duel(
        [task],
        providers,
        {},
        runs=2,
        on_update=lambda r: save_results(r, path),
        reuse=reuse,
        created_at=previous["created_at"],
    )
    assert (providers["a"].calls, providers["b"].calls) == (1, 1)  # solo la ronda 2
    assert results["status"] == "complete"
    assert results["created_at"] == previous["created_at"]
    a = results["tasks"][0]["results"]["a"]
    assert [x["run"] for x in a] == [1, 2] and all(x["solved"] for x in a)
    assert results["summary"]["a"]["tasks_solved"] == 1
    assert load_results(path)["status"] == "complete"


def test_reanudar_repite_los_errores_del_proveedor(make_task):
    task = make_task(ADD_TESTS)
    first = run_duel(
        [task],
        {"a": Provider("fake:a", ProviderError("HTTP 503")), "b": Provider("fake:b")},
        {},
    )
    assert first["tasks"][0]["results"]["a"][0]["status"] == "provider_error"
    reuse, _ = plan_resume(first, [task], {"a": "fake:a", "b": "fake:b"}, 1, first["timeout_s"])
    assert set(reuse) == {(task.id, "b", 1)}
    providers = _providers()
    second = run_duel([task], providers, {}, reuse=reuse)
    assert (providers["a"].calls, providers["b"].calls) == (1, 0)
    assert second["summary"]["a"]["tasks_solved"] == 1


def test_reanudar_recalcula_el_coste_con_los_precios_actuales(make_task):
    task = make_task(ADD_TESTS)
    first = run_duel([task], _providers(), {})
    assert first["tasks"][0]["results"]["a"][0]["cost"] is None  # sin precio
    reuse, _ = plan_resume(first, [task], {"a": "fake:a", "b": "fake:b"}, 1, first["timeout_s"])
    prices = {"fake:a": Price(input=1.0, output=2.0)}
    second = run_duel([task], _providers(), prices, reuse=reuse)
    assert second["tasks"][0]["results"]["a"][0]["cost"] == pytest.approx(0.0002)
    assert second["tasks"][0]["results"]["b"][0]["cost"] is None


# ---------------------------------------------------------------- compatibilidad


def _previous(make_task, **kwargs):
    task = make_task(ADD_TESTS)
    results = run_duel([task], _providers(), {}, **kwargs)
    return task, results


def test_contendientes_distintos_impiden_reanudar(make_task):
    task, previous = _previous(make_task)
    with pytest.raises(ResumeError, match=r"A: antes fake:a, ahora fake:otro"):
        plan_resume(previous, [task], {"a": "fake:otro", "b": "fake:b"}, 1, 20.0)
    with pytest.raises(ResumeError, match="C: antes"):
        plan_resume(previous, [task], {"a": "fake:a", "b": "fake:b", "c": "fake:c"}, 1, 20.0)


def test_tarea_cambiada_se_repite_entera_con_aviso(make_task):
    task, previous = _previous(make_task)
    (task.path / "task.md").write_text("Otro enunciado distinto.", encoding="utf-8")
    from modelduel.tasks import load_task

    changed = load_task(task.path)
    assert task_fingerprint(changed) != task_fingerprint(task)
    reuse, warnings = plan_resume(
        previous, [changed], {"a": "fake:a", "b": "fake:b"}, 1, previous["timeout_s"]
    )
    assert reuse == {}
    assert "«demo» ha cambiado" in warnings[0]


def test_aviso_si_cambian_timeout_ejecuciones_o_tareas(make_task):
    task, previous = _previous(make_task, runs=2)
    specs = {"a": "fake:a", "b": "fake:b"}
    reuse, warnings = plan_resume(previous, [], specs, 1, 5.0)
    text = " ".join(warnings)
    assert reuse == {}
    assert "era 20 s y ahora es 5 s" in text
    assert "antes eran 2 ejecuciones" in text
    assert "«demo» ya no está" in text
    reuse, _ = plan_resume(previous, [task], specs, 1, previous["timeout_s"])
    assert {k[2] for k in reuse} == {1}  # la ejecución 2 sobra


def test_resultados_sin_huella_se_aceptan(make_task):
    task, previous = _previous(make_task)
    del previous["tasks"][0]["fingerprint"]
    reuse, warnings = plan_resume(
        previous, [task], {"a": "fake:a", "b": "fake:b"}, 1, previous["timeout_s"]
    )
    assert len(reuse) == 2 and warnings == []


# ---------------------------------------------------------------- CLI de extremo a extremo


class _CutReplay:
    """Envuelve un proveedor replay y se corta con Ctrl+C en la llamada ``cut_at`` (global)."""

    calls = 0
    cut_at: int | None = None

    def __init__(self, inner):
        self.inner = inner
        self.spec = inner.spec

    def complete(self, prompt, *, task_id=None):
        type(self).calls += 1
        if type(self).calls == type(self).cut_at:
            raise KeyboardInterrupt
        return self.inner.complete(prompt, task_id=task_id)


@pytest.fixture
def cli_args(examples_dir, tmp_path):
    out = tmp_path / "duelo"
    args = [
        "run",
        str(examples_dir / "tasks"),
        "--a",
        "replay:alfa",
        "--b",
        "replay:beta",
        "--out",
        str(out),
    ]
    return args, out


@pytest.fixture
def cut(monkeypatch):
    _CutReplay.calls = 0
    _CutReplay.cut_at = None

    def fake_get(spec, replay_dirs=None, retries=3, on_retry=None):
        return _CutReplay(get_provider(spec, replay_dirs))

    monkeypatch.setattr("modelduel.cli.get_provider", fake_get)
    return _CutReplay


def test_cli_ctrl_c_deja_parcial_e_informe_y_resume_lo_completa(cli_args, cut, capsys):
    args, out = cli_args
    cut.cut_at = 4  # 3 tareas x 2 contendientes = 6 llamadas; se corta en la cuarta
    assert main(args) == 130
    captured = capsys.readouterr()
    assert "--resume" in captured.err
    partial = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert partial["status"] == "in_progress"
    done = sum(len(v) for t in partial["tasks"] for v in t["results"].values())
    assert done == 3
    assert "Duelo incompleto: 3 de 6 intentos" in (out / "index.html").read_text(encoding="utf-8")

    cut.calls, cut.cut_at = 0, None
    assert main([*args, "--resume"]) == 0
    printed = capsys.readouterr().out
    assert "Reanudando: 3 intentos ya hechos de 6; quedan 3." in printed
    assert printed.count("· ya hecho") == 3
    assert cut.calls == 3  # solo lo que faltaba
    final = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert final["status"] == "complete"
    assert final["summary"]["a"]["tasks_solved"] == 2
    assert final["summary"]["b"]["tasks_solved"] == 2
    assert "Duelo incompleto" not in (out / "index.html").read_text(encoding="utf-8")


def test_cli_sin_resume_no_machaca_un_duelo_incompleto(cli_args, cut, capsys):
    args, out = cli_args
    cut.cut_at = 2
    assert main(args) == 130
    capsys.readouterr()
    before = (out / "results.json").read_text(encoding="utf-8")
    cut.calls, cut.cut_at = 0, None
    assert main(args) == 2
    assert "incompleto" in capsys.readouterr().err
    assert cut.calls == 0
    assert (out / "results.json").read_text(encoding="utf-8") == before


def test_cli_sin_resume_sobrescribe_un_duelo_completo_o_ilegible(cli_args, cut):
    args, out = cli_args
    assert main(args) == 0
    assert main(args) == 0  # comportamiento de v0.1.0: se rehace
    (out / "results.json").write_text("{esto no es json", encoding="utf-8")
    assert main(args) == 0
    assert json.loads((out / "results.json").read_text(encoding="utf-8"))["status"] == "complete"


def test_cli_resume_sin_resultados_previos_empieza_de_cero(cli_args, cut, capsys):
    args, out = cli_args
    assert main([*args, "--resume"]) == 0
    assert "se empieza de cero" in capsys.readouterr().out
    assert (out / "results.json").is_file()


def test_cli_resume_de_un_duelo_completo_no_llama_a_nadie(cli_args, cut, capsys):
    args, _out = cli_args
    assert main(args) == 0
    cut.calls = 0
    capsys.readouterr()
    assert main([*args, "--resume"]) == 0
    assert cut.calls == 0
    assert "Reanudando: 6 intentos ya hechos de 6; quedan 0." in capsys.readouterr().out


def test_cli_resume_con_otros_contendientes_falla_con_mensaje(cli_args, cut, capsys):
    args, out = cli_args
    cut.cut_at = 2
    assert main(args) == 130
    capsys.readouterr()
    swapped = [*args]
    swapped[swapped.index("replay:beta")] = "replay:gamma"
    assert main([*swapped, "--resume"]) == 2
    assert "no coinciden" in capsys.readouterr().err
    assert json.loads((out / "results.json").read_text(encoding="utf-8"))["status"] == "in_progress"


def test_cli_resume_avisa_de_cambios_y_sigue(cli_args, cut, capsys):
    args, _out = cli_args
    cut.cut_at = 2
    assert main(args) == 130
    capsys.readouterr()
    cut.calls, cut.cut_at = 0, None
    assert main([*args, "--resume", "--timeout", "7"]) == 0
    assert "Aviso: el límite de los tests era 20 s y ahora es 7 s" in capsys.readouterr().out


def test_cli_si_falla_el_guardado_intermedio_el_duelo_sigue(cli_args, cut, capsys, monkeypatch):
    args, out = cli_args
    from modelduel import cli

    real = cli.save_results
    state = {"n": 0}

    def flaky(results, path):
        state["n"] += 1
        if state["n"] <= 3:
            raise OSError(28, "No space left on device")
        real(results, path)

    monkeypatch.setattr(cli, "save_results", flaky)
    assert main(args) == 0
    printed = capsys.readouterr().out
    assert printed.count("no se pudo guardar") == 1  # avisa una sola vez
    assert json.loads((out / "results.json").read_text(encoding="utf-8"))["status"] == "complete"


# ---------------------------------------------------------------- QA: casos límite


def _partial(cli_args, cut):
    args, out = cli_args
    cut.cut_at = 2
    assert main(args) == 130
    cut.calls, cut.cut_at = 0, None
    return args, out


def _edit(out, mutate):
    path = out / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_resume_rechaza_un_results_json_de_un_formato_mas_nuevo(cli_args, cut, capsys):
    args, out = _partial(cli_args, cut)
    _edit(out, lambda d: d.update(schema=99))
    capsys.readouterr()
    assert main([*args, "--resume"]) == 2
    err = capsys.readouterr().err
    assert "formato 99" in err and "Actualiza modelduel" in err
    assert cut.calls == 0  # no se gasta ninguna llamada


def test_resume_avisa_si_el_duelo_es_de_otra_version(cli_args, cut, capsys):
    args, out = _partial(cli_args, cut)
    _edit(out, lambda d: d.update(version="0.0.1"))
    capsys.readouterr()
    assert main([*args, "--resume"]) == 0
    assert "se hizo con modelduel 0.0.1" in capsys.readouterr().out


@pytest.mark.parametrize(
    "mutate",
    [
        lambda d: d["tasks"][0]["results"]["a"][0].pop("status"),
        lambda d: d.update(timeout_s="20"),
    ],
)
def test_resume_con_un_results_json_manipulado_no_da_traza(cli_args, cut, capsys, mutate):
    args, out = _partial(cli_args, cut)
    _edit(out, mutate)
    capsys.readouterr()
    code = main([*args, "--resume"])
    assert code in (0, 2)  # sigue o explica; nunca una traza de Python
    assert "Traceback" not in capsys.readouterr().err


@pytest.mark.parametrize("raw", ["", '{"schema": 1, "tasks": [', "[]", "null"])
def test_resume_con_un_results_json_corrupto_explica_y_no_gasta_llamadas(
    cli_args, cut, capsys, raw
):
    args, out = cli_args
    out.mkdir(parents=True)
    (out / "results.json").write_text(raw, encoding="utf-8")
    assert main([*args, "--resume"]) == 2
    assert "results.json" in capsys.readouterr().err
    assert cut.calls == 0


def test_un_error_del_proveedor_con_sustituto_suelto_no_tumba_el_guardado(make_task, tmp_path):
    """Un detalle de error con ``\ud800`` (válido en JSON) rompía ``save_results`` a mitad."""
    task = make_task(ADD_TESTS)
    boom = ProviderError("fallo \ud800 raro")
    path = tmp_path / "results.json"
    results = run_duel(
        [task], {"a": Provider("fake:a", answer=boom), "b": Provider("fake:b")}, {},
        on_update=lambda r: save_results(r, path),
    )  # fmt: skip
    assert results["status"] == "complete"
    assert "fallo" in load_results(path)["tasks"][0]["results"]["a"][0]["message"]


def test_save_results_no_deja_el_temporal_si_el_json_no_se_puede_escribir(tmp_path):
    path = tmp_path / "results.json"
    save_results({"tasks": [], "contenders": {}}, path)
    with pytest.raises((TypeError, ValueError, UnicodeEncodeError)):
        save_results({"x": object()}, path)
    assert not list(tmp_path.glob("*.tmp"))
    assert json.loads(path.read_text(encoding="utf-8")) == {"tasks": [], "contenders": {}}


def test_save_results_usa_os_replace_de_verdad_sobre_un_archivo_existente(tmp_path):
    """Sin simulaciones: en Windows ``os.replace`` sobre un destino existente debe funcionar."""
    path = tmp_path / "results.json"
    for i in range(3):
        save_results({"tasks": [], "contenders": {}, "n": i}, path)
    assert json.loads(path.read_text(encoding="utf-8"))["n"] == 2
    assert [p.name for p in tmp_path.iterdir()] == ["results.json"]


def test_ctrl_c_respeta_el_formato_pedido(cli_args, cut):
    args, out = cli_args
    cut.cut_at = 4
    assert main([*args, "--format", "md"]) == 130
    assert "Duelo incompleto: 3 de 6 intentos" in (out / "informe.md").read_text(encoding="utf-8")
    assert not (out / "index.html").exists()


def test_ctrl_c_con_html_y_md_escribe_los_dos(cli_args, cut):
    args, out = cli_args
    cut.cut_at = 4
    assert main([*args, "--format", "html,md"]) == 130
    assert (out / "index.html").is_file() and (out / "informe.md").is_file()
