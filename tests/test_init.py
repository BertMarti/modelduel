"""``modelduel init`` y ``modelduel run`` con ``modelduel.toml`` (fase 2, 24/10/2026)."""

from __future__ import annotations

import json
import tomllib

import pytest

from modelduel.cli import EXIT_USAGE, main
from modelduel.config import ConfigError, init_specs, load_config, render_config


def test_init_sin_proveedores_funciona_sin_claves(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    out = capsys.readouterr().out
    folder = tmp_path / "mi-duelo"
    assert (folder / "tasks").is_dir() and (folder / "replays").is_dir()
    assert "cd mi-duelo" in out and "modelduel run" in out
    data = tomllib.loads((folder / "modelduel.toml").read_text(encoding="utf-8"))
    assert data["modelos"] == ["replay:alfa", "replay:beta"]
    assert not list(folder.rglob("__pycache__"))

    # El primer duelo, sin argumentos y sin claves, desde la carpeta creada.
    monkeypatch.chdir(folder)
    for name in ("GEMINI_API_KEY", "OPENAI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    assert main(["run"]) == 0
    results = json.loads((folder / "resultados" / "results.json").read_text(encoding="utf-8"))
    assert [c["spec"] for c in results["contenders"].values()] == ["replay:alfa", "replay:beta"]
    assert (folder / "resultados" / "index.html").is_file()


def test_init_con_proveedores_explica_las_claves(tmp_path, capsys):
    target = tmp_path / "duelo"
    assert main(["init", str(target), "--proveedor", "gemini", "--provider", "openrouter"]) == 0
    out = capsys.readouterr().out
    assert 'export GEMINI_API_KEY="PEGA_AQUI_TU_CLAVE"' in out
    assert '$env:OPENAI_API_KEY = "PEGA_AQUI_TU_CLAVE"' in out
    assert "OPENAI_BASE_URL" in out and "https://openrouter.ai/keys" in out
    assert "cambia CAMBIA-ESTO" in out
    text = (target / "modelduel.toml").read_text(encoding="utf-8")
    assert tomllib.loads(text)["modelos"] == ["gemini:CAMBIA-ESTO", "openai:CAMBIA-ESTO"]
    assert "NUNCA van aquí" in text


def test_un_solo_proveedor_da_dos_contendientes():
    assert init_specs(["gemini"]) == ["gemini:CAMBIA-ESTO-1", "gemini:CAMBIA-ESTO-2"]
    assert init_specs(["ollama"]) == ["openai:CAMBIA-ESTO-1", "openai:CAMBIA-ESTO-2"]


def test_proveedores_que_comparten_variables_no_se_mezclan(tmp_path, capsys):
    argv = ["init", str(tmp_path / "x"), "--proveedor", "openai", "--proveedor", "ollama"]
    assert main(argv) == EXIT_USAGE
    err = capsys.readouterr().err
    assert "comparten OPENAI_BASE_URL" in err
    assert not (tmp_path / "x").exists()


def test_init_no_sobrescribe(tmp_path, capsys):
    assert main(["init", str(tmp_path)]) == 0
    toml = tmp_path / "modelduel.toml"
    toml.write_text("# mío\n", encoding="utf-8")
    assert main(["init", str(tmp_path)]) == EXIT_USAGE
    assert "no se sobrescribe" in capsys.readouterr().err
    assert toml.read_text(encoding="utf-8") == "# mío\n"


def test_init_no_machaca_tareas_existentes(tmp_path, capsys):
    (tmp_path / "tasks").mkdir()
    assert main(["init", str(tmp_path)]) == EXIT_USAGE
    assert "no se machacan" in capsys.readouterr().err


def test_proveedor_desconocido_es_error_de_uso(tmp_path, capsys):
    with pytest.raises(SystemExit) as info:
        main(["init", str(tmp_path), "--proveedor", "claudeai"])
    assert info.value.code == EXIT_USAGE


def test_la_plantilla_es_toml_valido_para_cada_proveedor(tmp_path):
    for name in ("gemini", "openai", "openrouter", "ollama", "omniroute"):
        path = tmp_path / f"{name}.toml"
        path.write_text(render_config(init_specs([name]), [name]), encoding="utf-8")
        assert len(load_config(path).models) == 2


def test_init_specs_rechaza_mezclas():
    with pytest.raises(ConfigError):
        init_specs(["openrouter", "openai"])
