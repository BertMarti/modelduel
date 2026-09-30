---
# Respuesta grabada y ficticia del contendiente «beta» (escrita a mano para la demo).
input_tokens: 459
output_tokens: 702
latency_s: 8.95
---
La idea es ordenar los intervalos por su inicio y recorrerlos una sola vez, ampliando el
último intervalo fusionado mientras el siguiente empiece antes de que termine (o justo
donde termina). La complejidad es O(n log n) por la ordenación.

```py
def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    """Fusiona intervalos cerrados que se solapan o comparten un extremo."""
    if not intervals:
        return []

    # Validamos antes de hacer nada para no devolver resultados parciales.
    for interval in intervals:
        start, end = interval
        if start > end:
            raise ValueError(f"El intervalo {interval!r} tiene inicio > fin")

    # sorted() crea una lista nueva, así que la entrada no se modifica.
    ordered = sorted(intervals, key=lambda item: item[0])

    result: list[tuple[int, int]] = [tuple(ordered[0])]
    for start, end in ordered[1:]:
        current_start, current_end = result[-1]
        if start <= current_end:  # se solapan o se tocan
            result[-1] = (current_start, max(current_end, end))
        else:
            result.append((start, end))
    return result
```

Con el ejemplo del enunciado, `[(8, 10), (1, 3), (2, 6), (15, 18)]` se ordena como
`[(1, 3), (2, 6), (8, 10), (15, 18)]` y el resultado es `[(1, 6), (8, 10), (15, 18)]`.
