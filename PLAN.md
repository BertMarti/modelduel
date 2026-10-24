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

## Siguiente
- **Límite de memoria en Windows:** Implementar `JOB_OBJECT_LIMIT_PROCESS_MEMORY` en el *Job Object* del runner para igualar la seguridad de POSIX.
- **Aislamiento en contenedores:** Añadir opción `--docker` o `--podman` para ejecutar los tests dentro de un contenedor si la herramienta está disponible, proporcionando un sandbox real.
- **Aislamiento de red en Linux:** Intentar usar `unshare -n` (namespaces de red) para desactivar el acceso a internet del código generado cuando el sistema lo permita.
- **Más tareas de ejemplo:** Ampliar `examples/tasks/` con retos de algoritmos más complejos y manipulación de datos (ej. JSON, CSV).
- **Resultados reales:** Poblar la carpeta `results/` con duelos reales entre modelos actuales para que la clasificación pública sea útil.
- **Procesos que se desligan:** una solución que llame a `setsid()` (o doble fork) sale del grupo de procesos y sobrevive al `killpg`. En Linux se podría usar `prctl(PR_SET_CHILD_SUBREAPER)` o un cgroup propio para recogerlos (revisión cruzada de GPT-5.6 Luna, 24/10/2026).
- **Disco:** `RLIMIT_FSIZE` limita cada archivo, no el total; valorar un tope de disco (cuota o contenedor).

## Ideas
- **Tareas multi-lenguaje:** Soporte experimental para tareas en JavaScript/TypeScript usando `node --test`.
- **Estimación de costes ampliada:** Añadir soporte para más monedas y actualización automática de precios vía API.
- **Histórico de resultados:** Gráficas de evolución de rendimiento de modelos a lo largo del tiempo en la clasificación pública.
- **Grafo interactivo:** Visualización de la liga de contendientes mediante un grafo de enfrentamientos directos (SVG interactivo).
