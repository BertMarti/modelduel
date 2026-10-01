import json
import subprocess
import sys

import pytest

from modelduel.cli import EXIT_ERROR, EXIT_USAGE, main
from tests.conftest import ROOT


def test_run_de_extremo_a_extremo_con_replay(examples_dir, tmp_path, capsys):
    out = tmp_path / "demo"
    code = main(
        [
            "run",
            str(examples_dir / "tasks"),
            "--a",
            "replay:alfa",
            "--b",
            "replay:beta",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    summary = results["summary"]
    # alfa: todo bien salvo un caso límite de parse_duration.
    assert summary["a"]["tasks_solved"] == 2
    assert summary["a"]["tests_passed"] == summary["a"]["tests_total"] - 1
    # beta: falla dos tests de slugify y resuelve el resto.
    assert summary["b"]["tasks_solved"] == 2
    assert summary["b"]["tests_passed"] == summary["b"]["tests_total"] - 2
    by_task = {t["id"]: t for t in results["tasks"]}
    assert not by_task["parse_duration"]["results"]["a"][0]["solved"]
    assert not by_task["slugify"]["results"]["b"][0]["solved"]
    assert summary["a"]["cost"] is not None and summary["a"]["fictitious_price"]

    html = (out / "index.html").read_text(encoding="utf-8")
    assert "Convertir una duración a segundos" in html
    assert "<script" not in html.lower()

    printed = capsys.readouterr().out
    assert "Contendiente" in printed and "Tests" in printed
    assert "precios ficticios" in printed


def test_run_una_tarea_y_varias_ejecuciones(examples_dir, tmp_path):
    out = tmp_path / "una"
    code = main(
        [
            "run",
            str(examples_dir / "tasks" / "merge_intervals"),
            "--a",
            "replay:alfa",
            "--b",
            "replay:beta",
            "--runs",
            "2",
            "--out",
            str(out),
        ]
    )
    assert code == 0
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert results["runs"] == 2
    assert len(results["tasks"][0]["results"]["a"]) == 2


def test_report_regenera_el_html(examples_dir, tmp_path):
    out = tmp_path / "r"
    args = ["run", str(examples_dir / "tasks" / "slugify"), "--a", "replay:alfa"]
    assert main([*args, "--b", "replay:beta", "--out", str(out)]) == 0
    (out / "index.html").unlink()
    assert main(["report", str(out / "results.json"), "--out", str(tmp_path / "otro")]) == 0
    assert (tmp_path / "otro" / "index.html").is_file()


def test_list_tasks(examples_dir, capsys):
    assert main(["list-tasks", str(examples_dir / "tasks")]) == 0
    printed = capsys.readouterr().out
    assert "slugify" in printed and "parse_duration" in printed


def test_errores_claros(examples_dir, tmp_path, capsys, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    tasks = str(examples_dir / "tasks")
    base = ["run", tasks, "--a", "replay:alfa", "--out", str(tmp_path)]
    assert main([*base, "--b", "gemini:modelo"]) == 2
    assert "GEMINI_API_KEY" in capsys.readouterr().err
    assert main([*base, "--b", "desconocido:x"]) == 2
    assert main([*base, "--b", "replay:beta", "--runs", "0"]) == 2
    assert main(["report", str(tmp_path / "no.json"), "--out", str(tmp_path)]) == 2
    assert main(["list-tasks", str(tmp_path / "vacio")]) == 2


def test_modulo_ejecutable():
    proc = subprocess.run(
        [sys.executable, "-m", "modelduel", "--version"], capture_output=True, text=True
    )
    assert proc.returncode == 0
    assert "modelduel" in proc.stdout


# ---------------------------------------------------------------- revisión qa


def _usage_error(argv, capsys) -> str:
    with pytest.raises(SystemExit) as info:
        main(argv)
    assert info.value.code == EXIT_USAGE
    return capsys.readouterr().err


def test_errores_de_argumentos_en_espanol(capsys):
    err = _usage_error(["run"], capsys)
    assert err.startswith("uso: modelduel run")
    assert "faltan argumentos obligatorios: tasks, --out" in err
    err = _usage_error(["run", "t", "--a", "x", "--b", "y", "--out", "o", "--runs", "dos"], capsys)
    assert "argumento --runs: valor no válido: 'dos'" in err
    err = _usage_error(["duelo"], capsys)
    assert "orden no válida: 'duelo'" in err
    err = _usage_error(["list-tasks", "x", "--sobra"], capsys)
    assert "argumentos no reconocidos: --sobra" in err
    assert "the following" not in err and "invalid" not in err


def test_ayuda_en_espanol(capsys):
    with pytest.raises(SystemExit) as info:
        main(["run", "--help"])
    assert info.value.code == 0
    out = capsys.readouterr().out
    assert out.startswith("uso: ")
    assert "opciones:" in out and "argumentos posicionales:" in out
    assert "muestra esta ayuda y sale" in out
    assert "usage" not in out and "show this help" not in out


def test_timeout_no_finito_se_rechaza(examples_dir, tmp_path, capsys):
    base = ["run", str(examples_dir / "tasks"), "--a", "replay:alfa", "--b", "replay:beta"]
    for bad in ("nan", "inf"):
        assert main([*base, "--timeout", bad, "--out", str(tmp_path / bad)]) == EXIT_USAGE
        assert "--timeout" in capsys.readouterr().err
        assert not (tmp_path / bad).exists()


def test_salida_que_no_se_puede_escribir(examples_dir, tmp_path, capsys):
    ocupado = tmp_path / "soy-un-archivo"
    ocupado.write_text("x", encoding="utf-8")
    args = ["run", str(examples_dir / "tasks" / "slugify"), "--a", "replay:alfa"]
    assert main([*args, "--b", "replay:beta", "--out", str(ocupado)]) == EXIT_ERROR
    err = capsys.readouterr().err
    assert err.startswith("modelduel: error: no se pudo escribir")
    assert "Traceback" not in err


def test_report_con_results_mal_formado(tmp_path, capsys):
    raro = tmp_path / "results.json"
    raro.write_text(
        json.dumps({"contenders": {"a": {}, "b": {}}, "tasks": [{"id": "x"}]}), encoding="utf-8"
    )
    assert main(["report", str(raro), "--out", str(tmp_path / "o")]) == EXIT_USAGE
    assert "no parece un results.json" in capsys.readouterr().err


def test_list_tasks_con_un_archivo(tmp_path, capsys):
    archivo = tmp_path / "x.txt"
    archivo.write_text("x", encoding="utf-8")
    assert main(["list-tasks", str(archivo)]) == EXIT_USAGE
    assert "no es una carpeta" in capsys.readouterr().err


def test_precios_y_results_con_bom(examples_dir, tmp_path):
    precios = tmp_path / "precios.json"
    precios.write_text('﻿{"replay:alfa": {"input": 1, "output": 2}}', encoding="utf-8")
    out = tmp_path / "o"
    args = ["run", str(examples_dir / "tasks" / "slugify"), "--a", "replay:alfa"]
    assert main([*args, "--b", "replay:beta", "--prices", str(precios), "--out", str(out)]) == 0
    results = out / "results.json"
    results.write_text("﻿" + results.read_text(encoding="utf-8"), encoding="utf-8")
    assert main(["report", str(results), "--out", str(tmp_path / "r")]) == 0


def test_leaderboard_genera_la_pagina(tmp_path, capsys):
    out = tmp_path / "lb"
    assert main(["leaderboard", str(ROOT / "results"), "--out", str(out)]) == 0
    assert (out / "index.html").is_file()
    assert any((out / "duelos").glob("*/index.html"))
    assert "index.html" in capsys.readouterr().out


def test_leaderboard_sin_resultados_es_error_de_uso(tmp_path, capsys):
    (tmp_path / "vacia").mkdir()
    assert (
        main(["leaderboard", str(tmp_path / "vacia"), "--out", str(tmp_path / "o")]) == EXIT_USAGE
    )
    assert "No hay resultados" in capsys.readouterr().err


def test_leaderboard_sin_permiso_de_escritura(tmp_path, capsys):
    bloqueo = tmp_path / "archivo"
    bloqueo.write_text("x", encoding="utf-8")  # --out cuelga de un archivo: no se puede crear
    code = main(["leaderboard", str(ROOT / "results"), "--out", str(bloqueo / "lb")])
    assert code == EXIT_ERROR
