---
# Respuesta grabada y ficticia del contendiente «beta» (escrita a mano para la demo).
input_tokens: 614
output_tokens: 745
latency_s: 11.93
---
```python
import heapq


def topo_order(deps: dict[str, list[str]]) -> list[str]:
    graph = {key: set(value) for key, value in deps.items()}
    for values in deps.values():
        graph.update({value: set() for value in values if value not in graph})
    available = [key for key, values in graph.items() if not values]
    heapq.heapify(available)
    result = []
    while available:
        current = heapq.heappop(available)
        result.append(current)
        for key, values in graph.items():
            values.discard(current)
            if not values and key not in result and key not in available:
                heapq.heappush(available, key)
    if len(result) != len(graph):
        raise ValueError("ciclo en las dependencias")
    return result
```
