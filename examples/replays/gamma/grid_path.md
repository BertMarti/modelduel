---
# Respuesta grabada y ficticia del contendiente «gamma» (escrita a mano para la demo).
input_tokens: 446
output_tokens: 205
latency_s: 1.27
---
```python
_DIRECTIONS = ((-1, 0), (1, 0), (0, -1), (0, 1))
_QUEUE = deque()


def grid_path(grid: list[str]) -> int:
    starts = [(r, c) for r, row in enumerate(grid) for c, value in enumerate(row) if value == "S"]
    ends = [(r, c) for r, row in enumerate(grid) for c, value in enumerate(row) if value == "E"]
    if len(starts) != 1 or len(ends) != 1:
        raise ValueError("Falta S o E")
    return -1
```
