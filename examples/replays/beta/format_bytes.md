---
# Respuesta grabada y ficticia del contendiente «beta» (escrita a mano para la demo).
input_tokens: 301
output_tokens: 387
latency_s: 3.91
---
He usado el formato habitual de JavaScript para redondear el valor:

```javascript
export function formatBytes(bytes, decimals = 1) {
  if (!Number.isFinite(bytes)) throw new TypeError("bytes no es finito");
  const unidades = ["B", "KiB", "MiB", "GiB", "TiB"];
  const negativo = bytes < 0;
  let valor = Math.abs(bytes);
  let indice = 0;
  while (valor >= 1024 && indice < unidades.length - 1) {
    valor /= 1024;
    indice += 1;
  }
  const texto = indice === 0 ? String(valor) : valor.toFixed(decimals);
  return `${negativo ? "-" : ""}${texto} ${unidades[indice]}`;
}
```
