# PLAN.md · modelduel

Hoja de ruta priorizada y realista para el desarrollo de modelduel. Lo hecho en cada versión, con detalle, está en `CHANGELOG.md`; aquí queda solo el resumen.

## Hecho en la fase 7 (02/11/2026, v1.2.0)
- **Grafo de enfrentamientos directos** (antes en «Ideas»): sección «Enfrentamientos directos» en el informe de duelo, en el de liga y en la clasificación pública. Grafo SVG (un nodo por modelo, una flecha por pareja del que gana más tareas al que gana menos, con el marcador y los empates), resaltado y panel de detalle al pasar el ratón, enfocar con el teclado o tocar, solo con CSS (los informes siguen sin JavaScript y con la misma CSP), leyenda y matriz de enfrentamientos en tabla como alternativa accesible. De 2 a 8 modelos con grafo; con más (solo posible en la clasificación), solo la tabla. Código en `report/h2h.py`, pruebas en `tests/test_h2h.py`.
- **Mantenimiento:** imagen de Python del contenedor a `python:3.13.18-slim` (por digest); `pip-audit` limpio; Dependabot sin PRs ni alertas abiertas; este PLAN resumido y sin puntos repetidos.

## Hecho antes (resumen)
- **v0.8.0 (24/10):** límites `setrlimit`, entorno sin secretos y `HOME` temporal en el runner; CSP estricta en informes, clasificación y portada; mypy, Python 3.13, gitleaks y pip-audit en el CI; Dependabot; `SECURITY.md`; README para usuarios y `docs/DESARROLLO.md`.
- **Fase 2 (24/10):** `modelduel init`, `modelduel.toml`, `modelduel doctor [--red]`; supervisor «subreaper» en Linux; CSP sin `'unsafe-inline'` (hash de cada `<style>`).
- **v0.9.0 (26/10):** `--sandbox docker|podman`, red cortada por defecto en Linux, límite de memoria en Windows, `--solo-generar` / `--replay`, ocho tareas de ejemplo.
- **v1.0.0 (26/10):** primera versión estable; `release.yml` pasa la suite y exige el CHANGELOG; documentado qué mide el marcador y qué no.
- **v1.1.0 (31/10):** tareas en JavaScript y TypeScript (experimental) por el mismo runner endurecido, con el modelo de permisos de Node.

## Siguiente (por prioridad)
1. **Resultados reales** en `results/` para que la clasificación pública (y su grafo) sea útil: duelos entre modelos actuales. Necesita claves y algo de gasto: decisión de Alberto.
2. **Probar `openai:` y `omniroute:` con una API real** (Gemini ya se usó de verdad). También necesita claves.
3. **JS/TS fuera de lo experimental:** probar en macOS (sin subreaper) y con Node anterior a la 20.15 (sin `--disable-wasm-trap-handler`, WebAssembly no cabe en el límite de memoria); valorar comprobar los tipos de TypeScript (haría falta `tsc`, una dependencia de npm) y `--sandbox-image` también para la imagen de Node.
4. **Resultados falsificables (límite de diseño; documentado en README, USO y SECURITY):** la solución corre en el mismo proceso que pytest o `node:test` y podría escribir un recuento falso; el aislamiento protege la máquina, no la honradez del marcador. Valorar sacar el recuento por otra vía (p. ej. un descriptor heredado solo por el ejecutor de tests) y comprobar que el número de tests coincide con el recogido antes de importar la solución.
5. **Entorno por lista blanca (baja):** `safe_env` quita lo que *parece* un secreto y deja pasar el resto (p. ej. `ANTHROPIC_BASE_URL` o el `PATH` del anfitrión). Valorar una lista blanca (`PATH` mínimo, idioma, `SYSTEMROOT` en Windows…) para Python y Node, sin romper pytest instalado con `--user`.
6. **Disco (baja; documentado):** `RLIMIT_FSIZE` limita cada archivo, no el total, y el contenedor monta la carpeta de la ejecución sin tope; valorar copiar los archivos a un tmpfs del contenedor (`docker create` + `docker cp`) o un volumen con cuota.
7. **Procesos que se desligan en macOS (baja; documentado):** no hay subreaper; valorar recorrer los procesos con la marca `MODELDUEL_RUN` (`ps -E`) también allí.
8. **Contenedor sin el pytest del anfitrión:** imagen propia con pytest (publicada en GHCR) para no depender de montar los paquetes del entorno local.
9. **Imágenes fijadas** (`DEFAULT_IMAGE` y `NODE_IMAGE` en `sandbox.py`): Dependabot no ve esas constantes; actualizarlas a mano cuando salga un parche (cómo, en `docs/DESARROLLO.md`).

## Ideas
- **Enfrentamientos directos en el informe Markdown:** la matriz como tabla de `informe.md` (con el mismo escapado de `md_text`).
- **Estimación de costes ampliada:** más monedas y precios actualizados desde una fuente pública.
- **Histórico de resultados:** gráficas de la evolución de cada modelo en la clasificación pública.
