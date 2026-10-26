# PLAN.md · modelduel

Hoja de ruta priorizada y realista para el desarrollo de modelduel.

## Hecho hoy (24/10/2026, v0.8.0)
- **Seguridad en el runner:**
  - Implementación de límites `setrlimit` en POSIX: 4 GiB de espacio de direcciones (solo Linux), CPU (con margen y SIGXCPU), archivos de máx. 256 MiB, 256 descriptores de archivos y desactivación de volcados de memoria (core).
  - Redirección de `HOME` y variables `XDG_*` a un directorio temporal de ejecución para evitar fugas de configuración personal.
  - Filtrado estricto de variables de entorno sensibles (claves, tokens, cookies, DSN, etc.) antes de ejecutar el código del modelo.
  - Mensajes de error específicos cuando el proceso es terminado por señales del sistema (SIGXCPU, SIGXFSZ, etc.).
- **Interfaz y Accesibilidad:**
  - Política de Seguridad de Contenido (CSP) estricta en informes, clasificación y portada para prohibir la ejecución de JavaScript no autorizado.
  - Navegación móvil de la portada en dos filas con zona táctil; en los informes y la clasificación, columna «Pos.» estrecha y pie de tabla dentro de la pantalla.
- **Calidad y CI/CD:**
  - Tipado estático con `mypy` sin errores y comprobación integrada en el CI.
  - El CI prueba también Python 3.13 (antes un test no se recogía en 3.13).
  - Auditoría de seguridad automatizada con `gitleaks` (secretos) y `pip-audit` (dependencias vulnerables).
  - Configuración de Dependabot para actualizaciones automáticas de dependencias de desarrollo y acciones de GitHub.
  - Nueva política de seguridad en `SECURITY.md`.
  - Permisos por job en los flujos de trabajo de GitHub Actions (`deploy.yml`) siguiendo el principio de mínimo privilegio.
- **Documentación:**
  - README renovado con banner, capturas de pantalla y secciones claras para usuarios.
  - Nueva guía técnica `docs/DESARROLLO.md`.

## Hecho en la fase 2 (24/10/2026, tarde)
- `modelduel init`, `modelduel.toml` (leído por `run`) y `modelduel doctor [--red]`; `modelduel` sin orden muestra los primeros pasos; errores de claves con la orden para definirlas.
- Supervisor «subreaper» en Linux: los procesos con `setsid`/doble fork ya no sobreviven (pendiente de ayer).
- CSP sin `'unsafe-inline'` en `style-src` (hash de cada `<style>`).
- README: prueba en una orden con entorno virtual, flujo `init` → `doctor` → `run` y orden `docker run` para código no fiable.

## Hecho en la fase 3 (26/10/2026, v0.9.0)
- **Aislamiento en contenedores:** `--sandbox docker|podman` (imagen oficial fijada por digest, sin red ni privilegios, solo lectura, techos de memoria, CPU y procesos) y clave `aislamiento` en `modelduel.toml`.
- **Aislamiento de red en Linux:** red cortada por defecto con espacios de nombres de usuario y red (sin root); aviso si el sistema no lo permite.
- **Límite de memoria en Windows:** `JOB_OBJECT_LIMIT_PROCESS_MEMORY` (1 GiB por proceso) en el Job Object, probado en el CI de Windows.
- **Modo «solo generar»:** `--solo-generar` y `--replay CARPETA`.
- **Más tareas de ejemplo:** `flatten_json`, `csv_totals`, `wrap_text`, `grid_path` y `topo_order` (8 en total).
- `modelduel doctor` informa del aislamiento disponible y recomienda el mejor.

## Siguiente
- **Resultados reales:** Poblar la carpeta `results/` con duelos reales entre modelos actuales para que la clasificación pública sea útil (necesita claves y gasto: decisión de Alberto).
- **Disco:** `RLIMIT_FSIZE` limita cada archivo, no el total, y el contenedor monta la carpeta de la ejecución sin tope; valorar copiar los archivos a un tmpfs del contenedor (`docker create` + `docker cp`) o un volumen con cuota.
- **Procesos que se desligan en macOS:** no hay subreaper; valorar recorrer los procesos con la marca `MODELDUEL_RUN` (`ps -E`) también allí.
- **Contenedor sin el pytest del anfitrión:** opción de imagen propia con pytest (publicada en GHCR) para no depender de montar los paquetes del entorno local.
- **Resultados falsificables (ya existía):** el código de la solución corre en el mismo proceso que pytest y puede escribir un `junit.xml` falso (o tocar pytest) para «aprobar»; en el contenedor, `/sandbox` (donde va el XML) es escribible. El aislamiento protege la máquina, no la honradez del marcador: valorar sacar el XML por otra vía (p. ej. un descriptor heredado solo por pytest) y comprobar que el número de tests coincide con el recogido antes de importar la solución.
- **Actualizar la imagen fijada** cuando salga un parche de Python (Dependabot no ve la constante de `sandbox.py`; cómo hacerlo en `docs/DESARROLLO.md`).

## Ideas
- **Tareas multi-lenguaje:** Soporte experimental para tareas en JavaScript/TypeScript usando `node --test`.
- **Estimación de costes ampliada:** Añadir soporte para más monedas y actualización automática de precios vía API.
- **Histórico de resultados:** Gráficas de evolución de rendimiento de modelos a lo largo del tiempo en la clasificación pública.
- **Grafo interactivo:** Visualización de la liga de contendientes mediante un grafo de enfrentamientos directos (SVG interactivo).
