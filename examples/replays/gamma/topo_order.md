---
# Respuesta grabada y ficticia del contendiente «gamma» (escrita a mano para la demo).
input_tokens: 462
output_tokens: 199
latency_s: 1.38
---
```python
def topo_order(deps: dict[str, list[str]]) -> list[str]:
    graph = {key: set(value) for key, value in deps.items()}
    for values in deps.values():
        for value in values:
            graph.setdefault(value, set())
    result = []
    while graph:
        ready = sorted(key for key, values in graph.items() if not values)
        if not ready:
            raise ValueError("ciclo detectado")
        for key in ready:
            result.append(key)
            del graph[key]
        for values in graph.values():
            values.difference_update(ready)
    return result
```
