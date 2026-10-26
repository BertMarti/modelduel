"""Aislamiento en la configuración, en ``init``, en la CLI y en ``doctor`` (tests extra).

Ningún test arranca Docker ni Podman: ``tests/conftest.py`` los oculta del PATH salvo con
``MODELDUEL_TEST_DOCKER=1``. Aquí se comprueba el contrato de la clave «aislamiento», la
precedencia de la orden y los textos que se enseñan a la persona usuaria.
"""

from __future__ import annotations

import shutil

import pytest

from modelduel.cli import EXIT_USAGE, main
from modelduel.config import ConfigError, init_project, load_config
from modelduel.doctor import collect_checks
from modelduel.sandbox import Sandbox

BASE = 'tareas = "tasks"\nmodelos = ["replay:alfa", "replay:beta"]\n'


def _write(tmp_path, text: str):
    path = tmp_path / "modelduel.toml"
    path.write_text(text, encoding="utf-8")
    return path


# ---------------------------------------------------------------- load_config


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("auto", "auto"),
        ("docker", "docker"),
        ("podman", "podman"),
        ("ninguno", "ninguno"),
        ("AUTO", "auto"),
        ("Docker", "docker"),
        ("  Podman  ", "podman"),
    ],
)
def test_aislamiento_valido_se_normaliza_a_minusculas(tmp_path, value, expected):
    config = load_config(_write(tmp_path, BASE + f'aislamiento = "{value}"\n'))
    assert config.sandbox == expected


def test_aislamiento_invalido_nombra_los_validos(tmp_path):
    path = _write(tmp_path, BASE + 'aislamiento = "kvm"\n')
    with pytest.raises(ConfigError) as info:
        load_config(path)
    message = str(info.value)
    assert "auto, docker, podman, ninguno" in message
    assert "«kvm»" in message and str(path) in message


def test_aislamiento_con_tipo_incorrecto_es_error_de_configuracion(tmp_path):
    path = _write(tmp_path, BASE + "aislamiento = 3\n")
    with pytest.raises(ConfigError) as info:
        load_config(path)
    message = str(info.value)
    assert "«aislamiento» debe ser" in message
    assert "auto, docker, podman, ninguno" in message and str(path) in message


# ---------------------------------------------------------------- modelduel init


def test_init_deja_el_aislamiento_comentado_y_la_configuracion_carga(tmp_path):
    target = tmp_path / "x"
    init_project(target, [])
    text = (target / "modelduel.toml").read_text(encoding="utf-8")
    assert '# aislamiento = "docker"' in text
    config = load_config(target / "modelduel.toml")
    # Comentada: manda el modo automático, no el contenedor.
    assert config.sandbox is None


# ---------------------------------------------------------------- run + configuración


@pytest.fixture
def proyecto(tmp_path, examples_dir, monkeypatch):
    shutil.copytree(examples_dir / "tasks" / "slugify", tmp_path / "tasks" / "slugify")
    (tmp_path / "modelduel.toml").write_text(
        'tareas = "tasks/slugify"\n'
        'modelos = ["replay:alfa", "replay:beta"]\n'
        'salida = "res"\n'
        'aislamiento = "docker"\n',
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    return tmp_path


def test_run_con_aislamiento_docker_ausente_sale_con_error_de_uso(proyecto, examples_dir, capsys):
    code = main(["run", "--replays", str(examples_dir / "replays")])
    assert code == EXIT_USAGE
    err = capsys.readouterr().err
    assert "no encuentro «docker»" in err
    assert not (proyecto / "res").exists()


def test_la_orden_sandbox_ninguno_manda_sobre_la_configuracion(proyecto, examples_dir, capsys):
    code = main(["run", "--sandbox", "ninguno", "--replays", str(examples_dir / "replays")])
    assert code == 0
    out = capsys.readouterr().out
    assert "Aviso: --sandbox ninguno" in out
    assert (proyecto / "res" / "results.json").is_file()


# ---------------------------------------------------------------- Sandbox.describe


def test_describe_un_contenedor():
    text = Sandbox(kind="docker", executable="/usr/bin/docker").describe()
    assert text.startswith("contenedor docker sin red")
    assert "sin privilegios" in text and "solo lectura" in text


def test_describe_la_red_cortada():
    text = Sandbox(isolate_network=True).describe()
    assert "red cortada" in text
    assert "temporal, entorno limpio y límites" in text


def test_describe_sin_red_cortada_avisa_de_la_red():
    text = Sandbox().describe()
    assert "CON red" in text
    assert "temporal, entorno limpio y límites" in text


# ---------------------------------------------------------------- doctor


def test_doctor_incluye_el_grupo_de_aislamiento_con_recomendacion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # que no encuentre un modelduel.toml del repositorio
    checks = collect_checks(env={})
    group = [check for check in checks if check.group == "Aislamiento disponible"]
    assert group
    assert any("recomendado" in check.text for check in group)
