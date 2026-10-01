"""Señal de vida durante las llamadas largas a un proveedor (sin esperas reales)."""

from __future__ import annotations

import threading

import pytest

from modelduel.duel import run_duel
from modelduel.heartbeat import Heartbeat
from modelduel.providers import ProviderError, Response
from tests.conftest import ADD_TESTS

CORRECT = "```python\ndef add(a, b):\n    return a + b\n```"


class _Clock:
    """Reloj falso: avanza 10 s en cada lectura (la primera, al entrar, vale 0)."""

    def __init__(self):
        self.now = -10.0

    def __call__(self):
        self.now += 10.0
        return self.now


def test_emite_el_tiempo_transcurrido_y_se_para_al_salir():
    lines: list[str] = []
    third = threading.Event()

    def emit(line):
        lines.append(line)
        if len(lines) == 3:
            third.set()

    with Heartbeat("gemini:x (tarea t)", emit, interval=0.001, clock=_Clock()):
        assert third.wait(5)
    assert lines[:3] == [
        "  ··  esperando a gemini:x (tarea t)… 10 s",
        "  ··  esperando a gemini:x (tarea t)… 20 s",
        "  ··  esperando a gemini:x (tarea t)… 30 s",
    ]


def test_una_llamada_corta_no_emite_nada():
    lines: list[str] = []
    with Heartbeat("x", lines.append, interval=3600):
        pass
    assert lines == []


def test_se_para_ante_una_excepcion_y_ante_ctrl_c():
    for error in (RuntimeError, KeyboardInterrupt):
        before = threading.active_count()
        with pytest.raises(error), Heartbeat("x", lambda _l: None, interval=3600):
            raise error()
        assert threading.active_count() == before


class _Slow:
    def __init__(self, spec):
        self.spec = spec

    def complete(self, prompt, *, task_id=None):
        return Response(text=CORRECT, input_tokens=1, output_tokens=1, latency_s=0.1)


class _Failing(_Slow):
    def complete(self, prompt, *, task_id=None):
        raise ProviderError("HTTP 503")


def test_el_duelo_avisa_con_proveedores_reales_pero_no_con_replay(make_task):
    labels: list[str] = []

    class _Spy:
        def __init__(self, label):
            labels.append(label)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    providers = {"a": _Slow("gemini:m"), "b": _Failing("openai:n"), "c": _Slow("replay:r")}
    task = make_task(ADD_TESTS)
    run_duel([task], providers, {}, heartbeat=_Spy)
    assert labels == [f"gemini:m (tarea {task.id})", f"openai:n (tarea {task.id})"]
