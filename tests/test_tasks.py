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
