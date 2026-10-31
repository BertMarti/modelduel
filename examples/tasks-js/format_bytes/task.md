# Formatear bytes con unidades binarias

Escribe una función de JavaScript con esta firma exacta:

```javascript
export function formatBytes(bytes, decimals = 1)
```

Debe formatear una cantidad de bytes usando unidades binarias y coma decimal
española siguiendo estas reglas:

1. `bytes` debe ser un número finito. Si no lo es (`NaN`, `Infinity` o
   `-Infinity`), lanza `TypeError`.
2. Usa unidades de base 1024, en este orden: `B`, `KiB`, `MiB`, `GiB` y
   `TiB`. Elige la unidad más grande cuyo valor absoluto sea al menos 1,
   salvo para valores menores de 1 KiB, que siempre se expresan en `B`.
3. Para `B` no se muestran decimales. Las demás unidades se redondean a
   `decimals` cifras decimales; `decimals` es un entero no negativo.
4. Se quitan los ceros que sobren al final de la parte decimal: `1,0 KiB` se
   escribe `1 KiB`. Se usa coma, nunca punto, como separador decimal.
5. Los valores negativos conservan el signo delante del número. El cero se
   escribe `0 B`.
6. La función es un módulo ES: exporta la función con `export function`.

Ejemplos:

- `formatBytes(512)` → `"512 B"`
- `formatBytes(1536)` → `"1,5 KiB"`
- `formatBytes(1024, 3)` → `"1 KiB"`
- `formatBytes(-2048, 0)` → `"-2 KiB"`
- `formatBytes(1048576)` → `"1 MiB"`
