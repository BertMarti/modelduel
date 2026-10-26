---
# Respuesta grabada y ficticia del contendiente «alfa» (escrita a mano para la demo).
input_tokens: 612
output_tokens: 356
latency_s: 4.72
---
```python
def flatten_json(data: dict) -> dict:
    result = {}

    def visit(value, prefix):
        if isinstance(value, dict):
            for key, child in value.items():
                if not isinstance(key, str):
                    raise TypeError("Las claves deben ser cadenas")
                if "." in key:
                    raise ValueError("Una clave contiene un punto")
                visit(child, f"{prefix}.{key}" if prefix else key)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                visit(child, f"{prefix}.{index}" if prefix else str(index))
        else:
            result[prefix] = value

    visit(data, "")
    return result
```
