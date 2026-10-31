---
# Respuesta grabada y ficticia del contendiente «gamma» (escrita a mano para la demo).
input_tokens: 326
output_tokens: 415
latency_s: 4.47
---
La función valida el número y recorta los ceros innecesarios:

```javascript
export function formatBytes(bytes, decimals = 1) {
  if (!Number.isFinite(bytes)) throw new TypeError("bytes debe ser finito");
  const unidades = ["B", "KiB", "MiB", "GiB", "TiB"];
  const negativo = bytes < 0;
  let valor = Math.abs(bytes);
  let indice = 0;
  while (valor >= 1024 && indice < unidades.length - 1) {
    valor /= 1024;
    indice += 1;
  }
  const cifras = indice === 0 ? 0 : decimals;
  const texto = valor.toFixed(cifras).replace(/(\.\d*?)0+$/, "$1").replace(/\.$/, "");
  return `${negativo ? "-" : ""}${texto.replace(".", ",")} ${unidades[indice]}`;
}
```
