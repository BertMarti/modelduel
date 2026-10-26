# Ordenar dependencias

Escribe una función de Python con esta firma exacta:

```python
def topo_order(deps: dict[str, list[str]]) -> list[str]:
```

`deps` indica las dependencias de cada elemento. Devuelve un orden topológico:
cada elemento aparece después de todas sus dependencias. Una dependencia que no
sea una clave de `deps` también debe aparecer en el resultado, sin dependencias
propias. Cuando haya varias opciones disponibles, elige siempre la que vaya
antes alfabéticamente, para que el resultado sea determinista.

Si las dependencias contienen un ciclo, lanza `ValueError` y el mensaje debe
contener la palabra `ciclo`. No modifiques `deps`.
