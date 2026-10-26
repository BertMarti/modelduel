---
# Respuesta grabada y ficticia del contendiente «alfa» (escrita a mano para la demo).
input_tokens: 527
output_tokens: 286
latency_s: 4.05
---
```python
import heapq


def topo_order(deps: dict[str, list[str]]) -> list[str]:
    graph = {node: set(values) for node, values in deps.items()}
    for values in deps.values():
        for value in values:
            graph.setdefault(value, set())
    result = []
    ready = [node for node, values in graph.items() if not values]
    heapq.heapify(ready)
    while ready:
        node = heapq.heappop(ready)
        result.append(node)
        for other in graph:
            if node in graph[other]:
                graph[other].remove(node)
                if not graph[other]:
                    heapq.heappush(ready, other)
    if len(result) != len(graph):
        raise ValueError("Se ha encontrado un ciclo")
    return result
```
