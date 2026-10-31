---
# Respuesta grabada y ficticia del contendiente «beta» (escrita a mano para la demo).
input_tokens: 333
output_tokens: 428
latency_s: 4.02
---
Agrupa cada elemento en un objeto de arrays:

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
