"""Orquestación del duelo con proveedores simulados (sin red)."""

from modelduel.duel import run_duel
from modelduel.providers import ProviderError, Response
from modelduel.report import render_report
from modelduel.results import load_results, save_results
from tests.conftest import ADD_TESTS

CORRECT = "```python\ndef add(a, b):\n    return a + b\n```"
WRONG = "```python\ndef add(a, b):\n    return 0\n```"


class FakeProvider:
    """Devuelve (o lanza) lo indicado en ``answers``, una entrada por llamada."""

    def __init__(self, spec, answers):
        self.spec = spec
        self.answers = list(answers)

    def complete(self, prompt, *, task_id=None):
        answer = self.answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return Response(text=answer, input_tokens=10, output_tokens=5, latency_s=0.5)


def test_varias_ejecuciones_agregan_bien(make_task):
    task = make_task(ADD_TESTS)
    providers = {
        "a": FakeProvider("fake:a", [CORRECT, WRONG]),
        "b": FakeProvider("fake:b", [CORRECT, CORRECT]),
    }
    results = run_duel([task], providers, {}, runs=2)
    a, b = results["summary"]["a"], results["summary"]["b"]
    assert [x["run"] for x in results["tasks"][0]["results"]["a"]] == [1, 2]
    # A resuelve solo la primera ejecución: la tarea no cuenta como resuelta.
    assert (a["tasks_solved"], a["attempts_solved"], a["attempts_total"]) == (0, 1, 2)
    assert (a["tests_passed"], a["tests_total"]) == (4, 6)  # 3 + 1 (add(0, 0) == 0)
    assert (b["tasks_solved"], b["attempts_solved"], b["tests_passed"]) == (1, 2, 6)
    assert a["input_tokens"] == 20 and a["latency_s"] == 1.0


def test_una_excepcion_inesperada_del_proveedor_no_tumba_el_duelo(make_task):
    task = make_task(ADD_TESTS)
    providers = {
        "a": FakeProvider("fake:a", [KeyError("choices"), CORRECT]),
        "b": FakeProvider("fake:b", [ProviderError("HTTP 500"), CORRECT]),
    }
    results = run_duel([task], providers, {}, runs=2)
    first_a, second_a = results["tasks"][0]["results"]["a"]
    assert first_a["status"] == "provider_error"
    assert "KeyError" in first_a["message"]
    assert second_a["solved"]
    assert results["tasks"][0]["results"]["b"][0]["message"] == "HTTP 500"


def test_texto_con_sustitutos_sueltos_no_rompe_resultados_ni_informe(make_task, tmp_path):
    # json.loads acepta "\ud83d" suelto; al escribir en UTF-8 lanzaba UnicodeEncodeError
    # al final del duelo y se perdían todos los resultados.
    task = make_task(ADD_TESTS)
    broken = "Aquí va \ud83d:\n" + CORRECT + "\n\ud800"
    no_code = "sin código \udfff"
    providers = {
        "a": FakeProvider("fake:a", [broken]),
        "b": FakeProvider("fake:b", [no_code]),
    }
    results = run_duel([task], providers, {})
    assert results["tasks"][0]["results"]["a"][0]["solved"]
    path = tmp_path / "results.json"
    save_results(results, path)
    reloaded = load_results(path)
    assert "sin código" in render_report(reloaded)
