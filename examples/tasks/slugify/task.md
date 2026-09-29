# Convertir un texto en slug

Escribe una función de Python con esta firma exacta:

```python
def slugify(text: str, separator: str = "-") -> str:
```

Debe convertir cualquier texto en un *slug* apto para una URL siguiendo estas reglas:

1. El resultado va en minúsculas.
2. Las letras con tilde, diéresis u otros diacríticos se convierten en su letra base
   (`á` → `a`, `ñ` → `n`, `ü` → `u`, `ç` → `c`).
3. Solo se conservan letras ASCII (`a`-`z`) y dígitos (`0`-`9`).
4. Cualquier secuencia de uno o más caracteres no conservados (espacios, signos de
   puntuación, barras, guiones, puntos…) se sustituye por **un único** `separator`.
5. El resultado nunca empieza ni termina con el separador.
6. Si no queda ningún carácter conservado, devuelve la cadena vacía `""`.

Ejemplos:

- `slugify("Canción de Añoranza")` → `"cancion-de-anoranza"`
- `slugify("Python 3.12 en 2026")` → `"python-3-12-en-2026"`
- `slugify("Árbol Genealógico", separator="_")` → `"arbol_genealogico"`
