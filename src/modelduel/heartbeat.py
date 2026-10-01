"""Señal de vida: avisa periódicamente de que una llamada larga sigue esperando respuesta."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable

HEARTBEAT_INTERVAL = 10.0


class Heartbeat:
    """Gestor de contexto: mientras dura el bloque, ``emit`` recibe una línea cada ``interval`` s.

    Una llamada más corta que ``interval`` no emite nada. El hilo se para siempre al salir
    (también ante un error o Ctrl+C). ``clock`` e ``interval`` son inyectables para los tests.
    """

    def __init__(
        self,
        label: str,
        emit: Callable[[str], None],
        interval: float = HEARTBEAT_INTERVAL,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._label = label
        self._emit = emit
        self._interval = interval
        self._clock = clock
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._start = 0.0

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            seconds = round(self._clock() - self._start)
            self._emit(f"  ··  esperando a {self._label}… {seconds} s")

    def __enter__(self) -> Heartbeat:
        self._start = self._clock()
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        self._thread.join()
