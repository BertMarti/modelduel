---
# Respuesta grabada y ficticia del contendiente «gamma» (escrita a mano para la demo).
input_tokens: 337
output_tokens: 439
latency_s: 4.61
---
Ordeno primero los elementos para que las claves queden agrupadas:

```typescript
export function groupBy<T, K extends string | number>(items: readonly T[], key: (item: T) => K): Record<K, T[]> {
  if (typeof key !== "function") throw new TypeError("key debe ser una función");
  const ordenados = (items as T[]).sort((a, b) => String(key(a)).localeCompare(String(key(b))));
  const grupos = {} as Record<K, T[]>;
  for (const item of ordenados) {
    const grupo = key(item);
    (grupos[grupo] ??= []).push(item);
  }
  return grupos;
}
```
