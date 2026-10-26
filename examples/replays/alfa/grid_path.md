---
# Respuesta grabada y ficticia del contendiente «alfa» (escrita a mano para la demo).
input_tokens: 541
output_tokens: 334
latency_s: 4.63
---
```python
from collections import deque


def grid_path(grid: list[str]) -> int:
    if not grid or any(len(row) != len(grid[0]) for row in grid):
        raise ValueError("Rejilla no rectangular")
    starts = [(r, c) for r, row in enumerate(grid) for c, value in enumerate(row) if value == "S"]
    ends = [(r, c) for r, row in enumerate(grid) for c, value in enumerate(row) if value == "E"]
    if len(starts) != 1 or len(ends) != 1 or any(ch not in "SE#." for row in grid for ch in row):
        raise ValueError("Rejilla no válida")
    queue = deque([(starts[0], 0)])
    seen = {starts[0]}
    while queue:
        (r, c), distance = queue.popleft()
        if (r, c) == ends[0]:
            return distance
        for nr, nc in ((r - 1, c), (r + 1, c), (r, c - 1), (r, c + 1)):
            if 0 <= nr < len(grid) and 0 <= nc < len(grid[0]) and grid[nr][nc] != "#" and (nr, nc) not in seen:
                seen.add((nr, nc))
                queue.append(((nr, nc), distance + 1))
    return -1
```
