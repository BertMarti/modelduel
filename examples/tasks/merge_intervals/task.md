# Fusionar intervalos

Escribe una función de Python con esta firma exacta:

```python
def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
```

Recibe una lista de intervalos **cerrados** `(inicio, fin)` de números enteros y devuelve
una lista nueva con los intervalos fusionados:

1. El resultado está ordenado por `inicio` y ningún par de intervalos del resultado se
   solapa ni se toca.
2. Dos intervalos que se solapan o que **comparten un extremo** se fusionan:
   `(1, 3)` y `(3, 5)` → `(1, 5)`.
3. Dos intervalos consecutivos que no comparten ningún punto **no** se fusionan:
   `(1, 2)` y `(3, 4)` siguen separados.
4. La entrada puede venir desordenada y puede contener intervalos de un solo punto,
   como `(5, 5)`.
5. La lista de entrada no se modifica.
6. Si algún intervalo tiene `inicio > fin`, lanza `ValueError`.
7. Una lista vacía devuelve `[]`.
8. Cada intervalo del resultado es una tupla `(inicio, fin)`.

Ejemplo:

```python
merge_intervals([(8, 10), (1, 3), (2, 6), (15, 18)])
# [(1, 6), (8, 10), (15, 18)]
```
