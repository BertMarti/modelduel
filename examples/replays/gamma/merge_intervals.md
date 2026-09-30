---
# Respuesta grabada y ficticia del contendiente «gamma» (escrita a mano para la demo).
input_tokens: 436
output_tokens: 142
latency_s: 1.21
---
```python
def merge_intervals(intervals: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(intervals):
        if start > end:
            raise ValueError(f"Intervalo no válido: {(start, end)}")
        if merged and start < merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged
```
