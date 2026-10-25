# Ajustar texto a líneas

Escribe una función de Python con esta firma exacta:

```python
def wrap_text(text: str, width: int) -> list[str]:
```

Reparte las palabras de `text` en líneas de como mucho `width` caracteres con
un algoritmo voraz: añade cada palabra a la línea actual si cabe, contando un
espacio entre palabras; si no cabe, empieza otra línea. Debe colapsar todos los
espacios y saltos de línea como separadores de palabras. Una palabra más larga
que `width` se parte en trozos consecutivos de `width` caracteres. El texto
vacío o formado solo por espacios devuelve `[]`. Si `width < 1`, lanza
`ValueError`.
