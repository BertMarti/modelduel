# Aplanar un objeto JSON

Escribe una función de Python con esta firma exacta:

```python
def flatten_json(data: dict) -> dict:
```

Recibe un objeto JSON ya cargado, representado por diccionarios, listas y valores
primitivos, y devuelve un diccionario nuevo que aplana todos los diccionarios y
listas anidados. Las claves resultantes se separan con puntos: una lista usa su
posición, por ejemplo `{"a": [{"b": 1}]}` produce `{"a.0.b": 1}`.

Un diccionario o una lista vacíos se conservan como valor en su propia clave.
El objeto raíz vacío devuelve `{}`. Las claves de diccionario deben ser cadenas y
no pueden contener un punto: en otro caso se lanza `ValueError` para el punto o
`TypeError` para una clave que no sea `str`. No se puede mutar `data` ni ninguno
de sus valores.
