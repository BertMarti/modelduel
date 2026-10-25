---
# Respuesta grabada y ficticia del contendiente «beta» (escrita a mano para la demo).
input_tokens: 559
output_tokens: 671
latency_s: 10.21
---
```python
def wrap_text(text: str, width: int) -> list[str]:
    if width < 1:
        raise ValueError("width inválido")
    words = text.split()
    result = []
    line = ""
    for word in words:
        while len(word) > width:
            if line:
                result.append(line)
                line = ""
            result.append(word[:width])
            word = word[width:]
        if word and line and len(line) + 1 + len(word) > width:
            result.append(line)
            line = ""
        if word:
            line = f"{line} {word}".strip()
    if line:
        result.append(line)
    return result
```
