---
# Respuesta grabada y ficticia del contendiente «beta» (escrita a mano para la demo).
input_tokens: 631
output_tokens: 702
latency_s: 10.84
---
Para recorrer cualquier combinación de diccionarios y listas conviene mantener el
prefijo actual y construir el resultado al encontrar valores hoja.

```
def flatten_json(data: dict) -> dict:
    result = {}

    def walk(value, prefix):
        if isinstance(value, dict):
            if not value:
                result[prefix] = {}
            for key, child in value.items():
                if not isinstance(key, str):
                    raise TypeError("clave no textual")
                if "." in key:
                    raise ValueError("punto en clave")
                walk(child, f"{prefix}.{key}" if prefix else key)
        elif isinstance(value, list):
            if not value:
                result[prefix] = []
            for index, child in enumerate(value):
                walk(child, f"{prefix}.{index}")
        else:
            result[prefix] = value

    walk(data, "")
    return result
```
