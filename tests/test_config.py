"""Lectura y validación de ``modelduel.toml`` y su precedencia frente a la orden (fase 2)."""

from __future__ import annotations

import shutil

import pytest

from modelduel.cli import EXIT_USAGE, main
from modelduel.config import ConfigError, load_config, placeholder_error, safe_url

BASE = 'tareas = "tasks"\nmodelos = ["replay:alfa", "replay:beta"]\n'


def _write(tmp_path, text: str):
    path = tmp_path / "modelduel.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_rutas_relativas_a_la_carpeta_del_archivo(tmp_path):
    config = load_config(_write(tmp_path, BASE + 'salida = "res"\nejecuciones = 2\n'))
    assert config.tasks == tmp_path / "tasks"
    assert config.out == tmp_path / "res"
    assert config.runs == 2 and config.timeout is None and config.format is None


@pytest.mark.parametrize(
    "text, fragment",
    [
        (BASE + "colores = 1\n", "clave desconocida «colores»"),
        ('tareas = "tasks"\n', "falta «modelos»"),
        (BASE + 'ejecuciones = "dos"\n', "«ejecuciones» debe ser un número entero"),
        (BASE + "ejecuciones = true\n", "«ejecuciones» debe ser un número entero"),
        (BASE + "ejecuciones = 0\n", "1 o más"),
        (BASE + "tiempo_limite = -1\n", "mayor que 0"),
        (BASE + "tiempo_limite = inf\n", "mayor que 0"),
        ('tareas = "t"\nmodelos = ["replay:alfa"]\n', "de 2 a 6 contendientes (tiene 1)"),
        ('tareas = "t"\nmodelos = ["a:1","b:2","c:3","d:4","e:5","f:6","g:7"]\n', "(tiene 7)"),
        ('tareas = "t"\nmodelos = ["replay:alfa", 3]\n', "lista de textos"),
        ("tareas = [\n", "no es un TOML válido"),
    ],
)
def test_errores_de_configuracion_claros(tmp_path, text, fragment):
    path = _write(tmp_path, text)
    with pytest.raises(ConfigError) as info:
        load_config(path)
    assert fragment in str(info.value)
    assert str(path) in str(info.value)


def test_falta_el_archivo(tmp_path):
    with pytest.raises(ConfigError, match="modelduel init"):
        load_config(tmp_path / "no.toml")


def test_marcador_cambia_esto():
    assert placeholder_error("replay:alfa", None) is None
    message = placeholder_error("gemini:CAMBIA-ESTO", None)
    assert message and "ai.google.dev" in message


def test_safe_url_quita_usuario_y_contrasena():
    assert safe_url("https://usu:secreta@ejemplo.test:8443/v1") == "https://ejemplo.test:8443/v1"
    assert safe_url("http://localhost:11434/v1") == "http://localhost:11434/v1"
    # Revisión cruzada: una clave en la consulta tampoco se muestra.
    assert safe_url("https://host.test/v1?token=SECRETO#x") == "https://host.test/v1?…"
    assert safe_url("no es una url") == "(URL no válida)"


# ---------------------------------------------------------------- run + configuración


@pytest.fixture
def proyecto(tmp_path, examples_dir, monkeypatch):
    shutil.copytree(examples_dir / "tasks", tmp_path / "tasks")
    shutil.copytree(examples_dir / "replays", tmp_path / "replays")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_run_lee_la_configuracion_y_la_orden_manda(proyecto, capsys):
    # Una sola tarea por velocidad: la orden manda sobre «tareas» y sobre los modelos.
    _write(proyecto, BASE + 'salida = "res"\nformato = "md"\n')
    code = main(["run", "tasks/slugify", "--a", "replay:gamma", "--b", "replay:beta"])
    assert code == 0
    out = capsys.readouterr().out
    assert "replay:gamma" in out and "replay:alfa" not in out
    assert (proyecto / "res" / "informe.md").is_file()  # formato del archivo
    assert not (proyecto / "res" / "index.html").exists()


def test_run_con_config_explicita(proyecto, tmp_path, capsys):
    other = proyecto / "otra"
    other.mkdir()
    (other / "duelo.toml").write_text(
        'tareas = "../tasks/slugify"\nmodelos = ["replay:alfa", "replay:beta"]\nsalida = "r"\n',
        encoding="utf-8",
    )
    assert main(["run", "--config", str(other / "duelo.toml")]) == 0
    assert (other / "r" / "index.html").is_file()


def test_run_sin_tareas_ni_configuracion_guia(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["run"]) == EXIT_USAGE
    err = capsys.readouterr().err
    assert "falta la carpeta de tareas" in err and "modelduel init" in err


def test_run_sin_salida_lo_explica(proyecto, capsys):
    code = main(["run", "tasks", "--a", "replay:alfa", "--b", "replay:beta"])
    assert code == EXIT_USAGE
    assert "falta --out" in capsys.readouterr().err


def test_run_con_marcador_explica_que_editar(proyecto, capsys):
    _write(proyecto, 'tareas = "tasks"\nmodelos = ["gemini:CAMBIA-ESTO", "replay:alfa"]\n')
    assert main(["run", "--out", "r"]) == EXIT_USAGE
    err = capsys.readouterr().err
    assert "edita modelduel.toml" in err and "CAMBIA-ESTO" in err
    assert not (proyecto / "r").exists()


def test_run_con_toml_roto_es_error_de_uso(proyecto, capsys):
    _write(proyecto, "modelos = [\n")
    assert main(["run"]) == EXIT_USAGE
    assert "no es un TOML válido" in capsys.readouterr().err


def test_demo_ignora_el_modelduel_toml_del_directorio(proyecto, capsys):
    _write(proyecto, "esto no es toml [\n")
    assert main(["demo", "--out", "d"]) == 0
    assert (proyecto / "d" / "index.html").is_file()


def test_sin_orden_muestra_los_primeros_pasos(capsys):
    assert main([]) == EXIT_USAGE
    out = capsys.readouterr().out
    assert "modelduel demo" in out and "modelduel init" in out and "modelduel doctor" in out


def test_falta_la_clave_explica_como_definirla(proyecto, monkeypatch, capsys):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    code = main(["run", "tasks", "--a", "gemini:m", "--b", "replay:alfa", "--out", "r"])
    assert code == EXIT_USAGE
    err = capsys.readouterr().err
    assert 'export GEMINI_API_KEY="PEGA_AQUI_TU_CLAVE"' in err
    assert "$env:GEMINI_API_KEY" in err and "Ayuda: modelduel doctor" in err
