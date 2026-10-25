# Sumar importes de un CSV

Escribe una función de Python con esta firma exacta:

```python
def csv_totals(text: str) -> dict[str, str]:
```

Recibe un texto CSV con una cabecera que contiene exactamente las columnas
`fecha`, `categoria` e `importe`. Las columnas pueden estar en cualquier orden y
la cabecera no distingue mayúsculas de minúsculas. Usa el módulo `csv` de la
biblioteca estándar: los campos entre comillas pueden contener comas.

Suma los importes con `decimal.Decimal` por categoría y devuelve cadenas con
exactamente dos decimales, por ejemplo `"12.50"`. Las claves del resultado deben
estar en orden alfabético. Las filas vacías se ignoran. Si falta una columna o
un importe no es un número válido, lanza `ValueError`.
