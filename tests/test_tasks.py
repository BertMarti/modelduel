import pytest

from modelduel.tasks import TaskError, count_tests, discover_tasks, load_task


def test_ejemplos_en_orden_de_dificultad(examples_dir):
    tasks = discover_tasks(examples_dir / "tasks")
    assert [t.id for t in tasks] == ["slugify", "merge_intervals", "parse_duration"]
    assert all(t.title and t.difficulty for t in tasks)
    assert all(t.expected_tests >= 5 for t in tasks)


def test_una_sola_tarea(examples_dir):
    tasks = discover_tasks(examples_dir / "tasks" / "slugify")
    assert [t.id for t in tasks] == ["slugify"]


def test_titulo_desde_el_enunciado(make_task):
    task = make_task("def test_a():\n    pass\n", statement="# Sumar\n\nTexto")
    assert task.title == "Sumar"


def test_meta_invalido(make_task):
    with pytest.raises(TaskError, match="TOML"):
        make_task("def test_a():\n    pass\n", meta="title = ")


def test_carpeta_sin_tareas(tmp_path):
    with pytest.raises(TaskError):
        discover_tasks(tmp_path)
    with pytest.raises(TaskError):
        discover_tasks(tmp_path / "no-existe")
    with pytest.raises(TaskError):
        load_task(tmp_path)


def test_count_tests_con_parametrize_y_clases():
    source = """
import pytest

def test_a(): pass

@pytest.mark.parametrize("x", [1, 2, 3])
def test_b(x): pass

class TestC:
    def test_d(self): pass
    def ayuda(self): pass

def ayuda(): pass
"""
    assert count_tests(source) == 5
    assert count_tests("def (") == 0


# ---------------------------------------------------------------- casos límite (qa)


def test_archivos_con_bom_de_windows(tmp_path):
    folder = tmp_path / "bom"
    folder.mkdir()
    bom = "﻿"
    (folder / "task.md").write_text(bom + "# Título con BOM\n\nTexto", encoding="utf-8")
    (folder / "test_task.py").write_text(
        bom + "from solution import f\n\ndef test_a():\n    assert f()\n", encoding="utf-8"
    )
    (folder / "meta.toml").write_text(bom + 'difficulty = "fácil"\n', encoding="utf-8")
    task = load_task(folder)
    assert task.title == "Título con BOM"
    assert not task.statement.startswith(bom)
    assert task.difficulty == "fácil"
    assert task.expected_tests == 1


def test_tests_con_error_de_sintaxis_se_rechazan_al_cargar(make_task):
    # Si no, el fallo de la tarea se atribuiría a los modelos como «no se pudo importar».
    with pytest.raises(TaskError, match="test_task.py"):
        make_task("from solution import add\n\ndef test_a(:\n    pass\n")


def test_count_tests_con_parametrize_de_constantes():
    source = """
import pytest

CASOS = [(1, 2), (3, 4), (5, 6)]
IDS = ("a", "b")

@pytest.mark.parametrize("x, y", CASOS)
def test_a(x, y): pass

@pytest.mark.parametrize("x", IDS)
@pytest.mark.parametrize("y", [1, 2])
def test_b(x, y): pass

@pytest.mark.parametrize(argnames="x", argvalues=[1, 2, 3, 4])
def test_c(x): pass
"""
    assert count_tests(source) == 3 + 4 + 4


def test_discover_con_un_archivo(tmp_path):
    archivo = tmp_path / "nota.txt"
    archivo.write_text("x", encoding="utf-8")
    with pytest.raises(TaskError, match="no es una carpeta"):
        discover_tasks(archivo)
