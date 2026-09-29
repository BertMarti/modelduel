import json
import subprocess
import sys

from modelduel.cli import main


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
    assert "Tests superados" in printed
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
