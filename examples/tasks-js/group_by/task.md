# Agrupar elementos por una clave

Escribe una función genérica de TypeScript con esta firma exacta:

```typescript
export function groupBy<T, K extends string | number>(
  items: readonly T[],
  key: (item: T) => K,
): Record<K, T[]>
```

Debe agrupar los elementos siguiendo estas reglas:

1. La clave de cada elemento es el resultado de llamar a `key` con ese
   elemento.
2. Los elementos de cada grupo conservan el orden en el que aparecieron en
   `items`.
3. No modifica la lista de entrada ni ninguno de sus elementos.
4. Devuelve un objeto sin propiedades (`{}`) si la lista está vacía.
5. Las claves pueden ser cadenas o números y se convierten en propiedades
   normales del objeto resultante.
6. Si `key` no es una función, lanza `TypeError`.
7. Es un módulo ES: exporta la función con `export function`.
8. Usa solo anotaciones de tipo que Node pueda borrar (nada de `enum`,
   `namespace` ni propiedades de parámetro en constructores).

Ejemplos:

- `groupBy(["ana", "alba", "bruno"], (nombre) => nombre[0])` →
  `{ a: ["ana", "alba"], b: ["bruno"] }`
- `groupBy([1, 2, 3, 4], (n) => n % 2)` → `{ 0: [2, 4], 1: [1, 3] }`
- `groupBy([], (valor) => valor)` → `{}`
