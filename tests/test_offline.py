"""Modo «solo generar» (``run --solo-generar``) y reproducción (``run --replay``)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from modelduel import runner
from modelduel.cli import EXIT_USAGE, main
from modelduel.providers import ProviderError, get_provider
from modelduel.providers.base import Response


@pytest.fixture
def tasks_dir(examples_dir, tmp_path) -> Path:
    """Dos tareas de ejemplo copiadas (para poder cambiarlas sin tocar el repo)."""
    target = tmp_path / "tareas-origen"
    for name in ("slugify", "merge_intervals"):
        shutil.copytree(examples_dir / "tasks" / name, target / name)
    return target


def _generate(tasks_dir: Path, out: Path, *extra: str, models=("replay:alfa", "replay:beta")):
    argv = ["run", str(tasks_dir), "--solo-generar", "--out", str(out)]
    for spec in models:
        argv += ["--model", spec]
    replays = Path(__file__).resolve().parent.parent / "examples" / "replays"
    return main([*argv, "--replays", str(replays), *extra])


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _solved(results: dict) -> dict:
    return {
        (task["id"], side): [a["passed"] for a in attempts]
        for task in results["tasks"]
        for side, attempts in task["results"].items()
    }


@pytest.fixture
def generated(tasks_dir, tmp_path, monkeypatch, capsys):
    """Respuestas generadas con replay, comprobando que no se ejecuta NADA."""

    def forbidden(*_args, **_kwargs):
        raise AssertionError("el modo solo generar no debe ejecutar código")

    monkeypatch.setattr(runner, "run_tests", forbidden)
    monkeypatch.setattr("modelduel.duel.run_tests", forbidden)
    monkeypatch.setattr("modelduel.cli.ensure_pytest_available", forbidden)
    out = tmp_path / "gen"
    assert _generate(tasks_dir, out) == 0
    printed = capsys.readouterr().out
    assert "no se ejecuta ningún código" in printed
    assert f"modelduel run --replay {out} --sandbox docker" in printed
    monkeypatch.undo()
    return out


def test_solo_generar_guarda_respuestas_y_tareas(generated):
    data = _load(generated / "respuestas.json")
    assert data["kind"] == "responses" and data["status"] == "complete" and data["runs"] == 1
    assert data["contenders"] == {"a": {"spec": "replay:alfa"}, "b": {"spec": "replay:beta"}}
    assert [t["id"] for t in data["tasks"]] == ["slugify", "merge_intervals"]
    first = data["tasks"][0]["attempts"]["a"][0]
    assert first["run"] == 1 and "def slugify" in first["response"]
    assert isinstance(first["latency_s"], float) and first["input_tokens"] > 0
    assert len(data["tasks"][0]["fingerprint"]) == 16
    assert (generated / "tareas" / "slugify" / "test_task.py").is_file()
    assert not (generated / "results.json").exists()


def test_replay_da_lo_mismo_que_un_duelo_normal(generated, tasks_dir, tmp_path, capsys):
    normal = tmp_path / "normal"
    argv = ["run", str(tasks_dir), "--model", "replay:alfa", "--model", "replay:beta"]
    assert main([*argv, "--out", str(normal)]) == 0
    assert main(["run", "--replay", str(generated)]) == 0  # salida por defecto: la carpeta
    printed = capsys.readouterr().out
    assert "no se llama a ninguna API" in printed
    replayed = _load(generated / "results.json")
    assert _solved(replayed) == _solved(_load(normal / "results.json"))
    assert replayed["contenders"]["a"]["spec"] == "replay:alfa"
    assert (generated / "index.html").is_file()


def test_replay_con_salida_y_tareas_explicitas(generated, tasks_dir, tmp_path):
    out = tmp_path / "otra"
    source = generated / "respuestas.json"
    assert (
        main(["run", str(tasks_dir / "slugify"), "--replay", str(source), "--out", str(out)]) == 0
    )
    assert [t["id"] for t in _load(out / "results.json")["tasks"]] == ["slugify"]


class FakeRemote:
    """Proveedor «real» falso: si se le llama al reproducir, el test falla."""

    calls = 0

    def __init__(self, spec: str, fail_on: str | None = None) -> None:
        self.spec = spec
        self.fail_on = fail_on

    def complete(self, prompt, *, task_id=None):
        FakeRemote.calls += 1
        if task_id == self.fail_on:
            raise ProviderError("HTTP 429: cuota agotada")
        name = task_id
        body = f"```python\ndef {name}(*args):\n    return None\n```"
        return Response(text=body, input_tokens=10, output_tokens=20, latency_s=1.5)


def test_el_spec_real_se_conserva_y_no_se_llama_a_ninguna_api(
    tasks_dir, tmp_path, monkeypatch, capsys
):
    def fake_get(spec, replay_dirs=None, retries=3, on_retry=None):
        if spec.startswith("replay:"):
            return get_provider(spec, replay_dirs)
        return FakeRemote(spec, fail_on="merge_intervals")

    monkeypatch.setattr("modelduel.cli.get_provider", fake_get)
    out = tmp_path / "gen"
    FakeRemote.calls = 0
    assert _generate(tasks_dir, out, models=("gemini:falso", "replay:alfa")) == 0
    assert FakeRemote.calls == 2
    data = _load(out / "respuestas.json")
    assert data["tasks"][1]["attempts"]["a"][0] == {"run": 1, "error": "HTTP 429: cuota agotada"}

    FakeRemote.calls = 0
    assert main(["run", "--replay", str(out), "--out", str(tmp_path / "res")]) == 0
    assert FakeRemote.calls == 0
    results = _load(tmp_path / "res" / "results.json")
    assert results["contenders"]["a"]["spec"] == "gemini:falso"
    merge = results["tasks"][1]["results"]["a"][0]
    assert merge["status"] == "provider_error" and "cuota agotada" in merge["message"]
    slug = results["tasks"][0]["results"]["a"][0]
    assert slug["latency_s"] == 1.5 and slug["output_tokens"] == 20
    assert "esperando" not in capsys.readouterr().err


def test_varias_ejecuciones_se_reproducen_cada_una(tasks_dir, tmp_path):
    out = tmp_path / "gen"
    assert _generate(tasks_dir, out, "--runs", "2") == 0
    data = _load(out / "respuestas.json")
    data["tasks"][0]["attempts"]["a"][1]["response"] = "sin código en la segunda"
    (out / "respuestas.json").write_text(json.dumps(data), encoding="utf-8")
    assert main(["run", "--replay", str(out)]) == 0
    attempts = _load(out / "results.json")["tasks"][0]["results"]["a"]
    assert [a["run"] for a in attempts] == [1, 2]
    assert attempts[0]["solved"] and attempts[1]["status"] == "no_code"


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d.update(kind="results"), "no es un respuestas.json"),
        (lambda d: d.update(schema=99), "no es un respuestas.json"),
        (lambda d: d.update(status="in_progress"), "se cortó"),
        (lambda d: d.update(runs=0), "ejecuciones"),
        (lambda d: d.update(runs=True), "ejecuciones"),
        (lambda d: d["contenders"].pop("b"), "entre 2 y 6"),
        (lambda d: d["contenders"].update(b={"spec": "replay:alfa"}), "repetidos"),
        (lambda d: d["contenders"].update(b={"spec": ""}), "repetidos"),
        (lambda d: d.update(contenders={"b": {"spec": "x"}, "a": {"spec": "y"}}), "orden"),
        (lambda d: d.update(tasks="nada"), "lista de tareas"),
        (lambda d: d["tasks"][0]["attempts"].update(a=[{"run": "1"}]), "intento inválido"),
        (lambda d: d["tasks"][0]["attempts"].update(a=[{"run": 1, "error": 3}]), "inválido"),
        (lambda d: d["tasks"].append(dict(d["tasks"][0])), "repetidas"),
    ],
)
def test_respuestas_hostiles_dan_error_de_uso_sin_traceback(generated, capsys, change, message):
    path = generated / "respuestas.json"
    data = _load(path)
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["run", "--replay", str(generated)]) == EXIT_USAGE
    err = capsys.readouterr().err
    assert message in err and "Traceback" not in err


def test_json_roto_o_ausente(tmp_path, capsys):
    broken = tmp_path / "respuestas.json"
    broken.write_text("{no es json", encoding="utf-8")
    assert main(["run", "--replay", str(broken)]) == EXIT_USAGE
    assert "no es un respuestas.json válido" in capsys.readouterr().err
    assert main(["run", "--replay", str(tmp_path / "nada")]) == EXIT_USAGE
    assert "--solo-generar" in capsys.readouterr().err


def test_tarea_no_grabada_es_error_y_tarea_cambiada_es_aviso(
    generated, examples_dir, tasks_dir, capsys
):
    other = examples_dir / "tasks" / "parse_duration"
    assert main(["run", str(other), "--replay", str(generated)]) == EXIT_USAGE
    assert "«parse_duration» no está" in capsys.readouterr().err

    statement = generated / "tareas" / "slugify" / "task.md"
    statement.write_text(statement.read_text(encoding="utf-8") + "\nCambio.", encoding="utf-8")
    assert main(["run", "--replay", str(generated)]) == 0
    assert "la tarea slugify cambió" in capsys.readouterr().out


@pytest.mark.parametrize(
    "extra",
    [
        ("--solo-generar", "--replay", "x"),
        ("--solo-generar", "--resume"),
        ("--solo-generar", "--sandbox", "docker"),
    ],
)
def test_combinaciones_prohibidas_al_generar(tasks_dir, tmp_path, capsys, extra):
    argv = ["run", str(tasks_dir), "--model", "replay:alfa", "--model", "replay:beta"]
    assert main([*argv, *extra, "--out", str(tmp_path / "o")]) == EXIT_USAGE
    assert "Traceback" not in capsys.readouterr().err
    assert not (tmp_path / "o" / "respuestas.json").exists()


def test_combinaciones_prohibidas_al_reproducir(generated, capsys):
    assert main(["run", "--replay", str(generated), "--model", "replay:alfa"]) == EXIT_USAGE
    assert "contendientes grabados" in capsys.readouterr().err
    assert main(["run", "--replay", str(generated), "--runs", "3"]) == EXIT_USAGE
    assert "no coincide" in capsys.readouterr().err


def test_una_generacion_a_medias_no_se_sobrescribe(generated, tasks_dir, capsys):
    path = generated / "respuestas.json"
    data = _load(path)
    data["status"] = "in_progress"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert _generate(tasks_dir, generated) == EXIT_USAGE
    assert "incompleta" in capsys.readouterr().err


def test_no_se_pisa_una_carpeta_tareas_ajena(tasks_dir, tmp_path, capsys):
    out = tmp_path / "gen"
    (out / "tareas").mkdir(parents=True)
    assert _generate(tasks_dir, out) == EXIT_USAGE
    assert "no es de una generación anterior" in capsys.readouterr().err


def test_resume_con_replay_reutiliza_los_intentos(generated, capsys):
    assert main(["run", "--replay", str(generated)]) == 0
    capsys.readouterr()
    assert main(["run", "--replay", str(generated), "--resume"]) == 0
    assert "4 intentos ya hechos de 4" in capsys.readouterr().out


@pytest.mark.parametrize(
    ("change", "message"),
    [
        (lambda d: d.update(runs=10**9), "de 1 a 100"),
        (
            lambda d: d["tasks"][0]["attempts"]["a"].append(
                dict(d["tasks"][0]["attempts"]["a"][0])
            ),
            "una sola vez",
        ),
        (lambda d: d["tasks"][0]["attempts"]["a"][0].update(run=2), "de 1 a 1"),
    ],
)
def test_ejecuciones_desmesuradas_o_repetidas_se_rechazan(generated, capsys, change, message):
    # Revisión cruzada (fase 3): un runs enorme en un respuestas.json ajeno bloqueaba el duelo.
    path = generated / "respuestas.json"
    data = _load(path)
    change(data)
    path.write_text(json.dumps(data), encoding="utf-8")
    assert main(["run", "--replay", str(generated)]) == EXIT_USAGE
    assert message in capsys.readouterr().err


def test_tareas_con_enlaces_simbolicos_se_rechazan(generated, tmp_path, capsys):
    # Un test_task.py enlazado a un archivo del anfitrión acabaría copiado junto a la solución.
    secreto = tmp_path / "secreto.txt"
    secreto.write_text("no debe salir", encoding="utf-8")
    enlace = generated / "tareas" / "slugify" / "datos.txt"
    try:
        enlace.symlink_to(secreto)
    except (OSError, NotImplementedError):
        pytest.skip("este sistema no deja crear enlaces simbólicos")
    assert main(["run", "--replay", str(generated)]) == EXIT_USAGE
    assert "enlace simbólico" in capsys.readouterr().err
    assert not (generated / "results.json").exists()


def test_tareas_demasiado_grandes_se_rechazan(generated, monkeypatch, capsys):
    monkeypatch.setattr("modelduel.offline.MAX_BUNDLE_BYTES", 10)
    assert main(["run", "--replay", str(generated)]) == EXIT_USAGE
    assert "demasiado grande" in capsys.readouterr().err
