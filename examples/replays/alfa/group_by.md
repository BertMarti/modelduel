---
# Respuesta grabada y ficticia del contendiente «alfa» (escrita a mano para la demo).
input_tokens: 329
output_tokens: 431
latency_s: 4.26
---
Esta implementación conserva el orden y no toca la entrada:

```typescript
export function groupBy<T, K extends string | number>(items: readonly T[], key: (item: T) => K): Record<K, T[]> {
  if (typeof key !== "function") throw new TypeError("key debe ser una función");
  const grupos = {} as Record<K, T[]>;
  for (const item of items) {
    const grupo = key(item);
    (grupos[grupo] ??= []).push(item);
  }
  return grupos;
}
```
