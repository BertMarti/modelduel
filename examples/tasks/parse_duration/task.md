# Convertir una duración a segundos

Escribe una función de Python con esta firma exacta:

```python
def parse_duration(text: str) -> int:
```

Recibe una duración escrita por una persona, como `"1h 30m 15s"`, y devuelve el total en
segundos (`5415` en ese ejemplo).

Formato válido:

1. La duración está formada por uno o más **componentes** `<entero><unidad>`, sin espacio
   entre el número y la unidad.
2. Las unidades son `d` (días), `h` (horas), `m` (minutos) y `s` (segundos), en
   minúsculas o mayúsculas.
3. Los componentes pueden ir juntos (`"1h30m"`) o separados por espacios, y se admiten
   espacios al principio y al final.
4. Cada unidad aparece **como mucho una vez** y siempre en orden descendente:
   `d`, luego `h`, luego `m`, luego `s`. Se pueden omitir unidades (`"2d 5s"` es válido).
5. El número es un entero sin signo; `"0s"` es válido y vale `0`.

Cualquier otra cosa debe lanzar `ValueError`, por ejemplo: cadena vacía o solo espacios,
un número sin unidad (`"10"`), una unidad desconocida (`"5x"`), una unidad repetida
(`"1h 2h"`), unidades fuera de orden (`"30m 1h"`), signos (`"-5m"`), decimales (`"1.5h"`)
o texto sobrante (`"1h y 5m"`).
