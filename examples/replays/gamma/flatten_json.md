---
# Respuesta grabada y ficticia del contendiente «gamma» (escrita a mano para la demo).
input_tokens: 474
output_tokens: 194
latency_s: 1.42
---
```python
def flatten_json(data: dict) -> dict:
    result = {}

    def walk(value, prefix):
        if isinstance(value, dict):
            for key, child in value.items():
                walk(child, prefix + "." + key if prefix else key)
        elif isinstance(value, list):
            for child in value:
                walk(child, prefix)
        else:
            result[prefix] = value

    walk(data, "")
    return result
```
