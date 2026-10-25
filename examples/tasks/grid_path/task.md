# Buscar un camino en una rejilla

Escribe una función de Python con esta firma exacta:

```python
def grid_path(grid: list[str]) -> int:
```

Recibe una rejilla de texto con una `S` (salida), una `E` (meta), `#` (muro) y
`.` (casilla libre). Devuelve el número mínimo de pasos desde `S` hasta `E`,
moviéndose solo arriba, abajo, izquierda o derecha. Devuelve `-1` si no existe
camino. No se puede atravesar un muro.

Lanza `ValueError` si no hay exactamente una `S` y una `E`, si las filas tienen
distinta longitud o si aparece cualquier carácter distinto de `S`, `E`, `#` y
`.`.
