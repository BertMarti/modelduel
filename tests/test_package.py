"""Empaquetado y publicación: metadatos, `modelduel demo` y el workflow de PyPI (sin red)."""

from __future__ import annotations

import json
import re
import tomllib

import pytest

from modelduel import __version__
from modelduel.cli import main
from modelduel.demo import DEMO_MODELS, examples_dir
from modelduel.tasks import TaskError
from tests.conftest import ROOT

PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
RELEASE = (ROOT / ".github" / "workflows" / "release.yml").read_text(encoding="utf-8")


# ---------------------------------------------------------------- metadatos


def test_la_version_sale_de_un_solo_sitio():
    project = PYPROJECT["project"]
    assert "version" not in project and "version" in project["dynamic"]
    assert PYPROJECT["tool"]["hatch"]["version"]["path"] == "src/modelduel/__init__.py"
    assert re.fullmatch(r"\d+\.\d+\.\d+", __version__)


def test_metadatos_completos_para_pypi():
    project = PYPROJECT["project"]
    assert project["name"] == "modelduel"
    assert project["readme"] == "README.md" and project["license"] == "MIT"
    assert project["license-files"] == ["LICENSE"]
    assert project["requires-python"] == ">=3.12"
    assert project["dependencies"] == []  # solo biblioteca estándar en ejecución
    assert project["scripts"] == {"modelduel": "modelduel.cli:main"}
    assert {"Homepage", "Documentation", "Source", "Issues"} <= set(project["urls"])
    assert len(project["description"]) < 200 and project["keywords"]
    for classifier in project["classifiers"]:
        assert classifier.count("::") >= 1
    assert any(c.startswith("Development Status") for c in project["classifiers"])
    assert "Natural Language :: Spanish" in project["classifiers"]
    extras = project["optional-dependencies"]
    assert extras["pytest"] == ["pytest>=8"] and "pytest>=8" in extras["dev"]


def test_los_ejemplos_viajan_dentro_de_la_wheel():
    wheel = PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["force-include"] == {"examples": "modelduel/examples"}
    sdist = PYPROJECT["tool"]["hatch"]["build"]["targets"]["sdist"]["include"]
    assert "/examples" in sdist and "/src" in sdist


def test_el_readme_no_tiene_enlaces_relativos_que_se_rompan_en_pypi():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    links = re.findall(r"\]\(([^)\s]+)\)", readme)
    assert links
    for link in links:
        assert link.startswith(("https://", "http://", "#")), f"enlace relativo: {link}"


# ---------------------------------------------------------------- workflow de publicación


def test_release_usa_trusted_publishing_sin_tokens():
    assert "release:" in RELEASE and "types: [published]" in RELEASE
    assert "id-token: write" in RELEASE
    assert "pypa/gh-action-pypi-publish@release/v1" in RELEASE
    assert re.search(r"environment:\s*\n\s+name: pypi", RELEASE)
    assert "twine check --strict" in RELEASE and "python -m build" in RELEASE
    # Ni secretos, ni contraseñas, ni usuario/token de PyPI.
    for forbidden in ("secrets.", "password", "PYPI_API_TOKEN", "__token__", "TWINE_"):
        assert forbidden not in RELEASE, forbidden


def test_solo_el_job_de_publicacion_puede_pedir_el_token_oidc():
    top, jobs = RELEASE.split("\njobs:\n")
    assert "id-token" not in top  # permisos globales mínimos
    build, publish = jobs.split("  publish:\n")
    assert "id-token" not in build
    assert "needs: build" in publish and "id-token: write" in publish


def test_el_ci_tambien_construye_y_comprueba_el_paquete():
    ci = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "python -m build" in ci and "twine check --strict" in ci
    assert "demo --out" in ci


# ---------------------------------------------------------------- modelduel demo


def test_examples_dir_encuentra_tareas_y_respuestas():
    folder = examples_dir()
    assert (folder / "tasks" / "slugify" / "task.md").is_file()
    for model in DEMO_MODELS:
        assert (folder / "replays" / model.split(":")[1]).is_dir()


def test_examples_dir_prefiere_los_ejemplos_del_paquete(tmp_path, monkeypatch):
    import modelduel.demo as demo

    package = tmp_path / "pkg" / "modelduel"
    (package / "examples" / "tasks").mkdir(parents=True)
    (package / "examples" / "replays").mkdir()
    monkeypatch.setattr(demo, "__file__", str(package / "demo.py"))
    assert examples_dir() == (package / "examples").resolve()


def test_examples_dir_sin_ejemplos_da_un_error_claro(tmp_path, monkeypatch):
    import modelduel.demo as demo

    (tmp_path / "a" / "b").mkdir(parents=True)
    monkeypatch.setattr(demo, "__file__", str(tmp_path / "a" / "b" / "demo.py"))
    with pytest.raises(TaskError, match="no encuentro los ejemplos"):
        examples_dir()


def test_demo_ejecuta_la_liga_de_tres(tmp_path, capsys):
    out = tmp_path / "demo"
    assert main(["demo", "--out", str(out)]) == 0
    results = json.loads((out / "results.json").read_text(encoding="utf-8"))
    assert [c["spec"] for c in results["contenders"].values()] == list(DEMO_MODELS)
    assert "Informe de liga" in (out / "index.html").read_text(encoding="utf-8")
    printed = capsys.readouterr().out
    assert "respuestas grabadas y precios ficticios" in printed


def test_demo_copy_copia_los_ejemplos_y_no_pisa_carpetas(tmp_path, capsys):
    target = tmp_path / "mis-ejemplos"
    assert main(["demo", "--copy", str(target)]) == 0
    assert (target / "tasks" / "parse_duration" / "test_task.py").is_file()
    assert (target / "replays" / "gamma" / "slugify.md").is_file()
    assert not list(target.rglob("__pycache__"))
    assert "Pruébalos con:" in capsys.readouterr().out
    assert main(["demo", "--copy", str(target)]) == 2  # ya existe y no está vacía
    assert "ya existe" in capsys.readouterr().err
    empty = tmp_path / "vacia"
    empty.mkdir()
    assert main(["demo", "--copy", str(empty)]) == 0  # una carpeta vacía sí vale


def test_demo_avisa_si_no_se_puede_copiar(tmp_path, monkeypatch, capsys):
    def boom(*_args, **_kwargs):
        raise OSError(13, "Permiso denegado")

    monkeypatch.setattr("modelduel.cli.shutil.copytree", boom)
    assert main(["demo", "--copy", str(tmp_path / "x")]) == 1
    assert "no se pudo copiar" in capsys.readouterr().err


def test_release_solo_publica_commits_de_main_y_no_guarda_credenciales():
    build = RELEASE.split("  publish:")[0]
    assert "merge-base --is-ancestor HEAD origin/main" in build
    assert "persist-credentials: false" in build and "fetch-depth: 0" in build


def test_la_wheel_incluye_todo_lo_que_necesita_modelduel_demo():
    """Lo que ``modelduel demo`` lee tiene que viajar en la wheel (``force-include``)."""
    folder = examples_dir()
    wheel = PYPROJECT["tool"]["hatch"]["build"]["targets"]["wheel"]
    assert wheel["force-include"]["examples"] == "modelduel/examples"
    assert folder.name == "examples" and folder == (ROOT / "examples")
    package = ROOT / "src" / "modelduel" / "report"
    for name in ("template.html", "league.html", "style.css"):
        assert (package / name).is_file()  # hatch incluye todo lo que hay bajo src/modelduel
    assert wheel["packages"] == ["src/modelduel"]
