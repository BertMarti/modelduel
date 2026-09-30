# AGENTS.md · modelduel

## Qué es
CLI que enfrenta a dos modelos de IA con la misma tarea de programación: les pide el código, ejecuta los tests de la tarea sobre cada respuesta y genera un informe HTML con aciertos, tiempo, tokens y coste estimado. Convierte en herramienta el ejercicio «tu propia comparativa» de la guía de modelos del curso.

## Tecnología (propia de este proyecto)
- **Python 3.12**, paquete instalable con `pyproject.toml` (backend `hatchling`).
- Solo biblioteca estándar en tiempo de ejecución (HTTP con `urllib`, CLI con `argparse`). Informe HTML con plantilla propia (`string.Template`) y **gráficas SVG en línea**, sin JavaScript.
- **pytest** para tests; **ruff** para lint y formato.
- Despliegue: **GitHub Pages** con la web del proyecto y un **informe de demostración** generado en el CI con respuestas grabadas (proveedor `replay`), sin claves.

## Comandos
- Entorno: `python -m venv .venv` y `pip install -e ".[dev]"`
- Lint: `ruff check . && ruff format --check .`
- Tests: `pytest`
- Demo: `modelduel run examples/tasks --a replay:alfa --b replay:beta --out site/demo`

## Estructura
- `src/modelduel/cli.py` punto de entrada.
- `src/modelduel/providers/` proveedores: `replay` (grabado), `gemini` (API de Google), `openai` (cualquier API compatible con OpenAI: OpenRouter, Ollama…).
- `src/modelduel/runner.py` extrae el código de la respuesta y ejecuta los tests en un directorio temporal con límite de tiempo.
- `src/modelduel/report/` informe HTML y JSON.
- `examples/tasks/` tareas de ejemplo originales (enunciado + tests) y `examples/replays/` respuestas grabadas.
- `site/` web estática del proyecto.

## Seguridad
El código generado por un modelo se ejecuta en local: siempre en un directorio temporal, en un subproceso con límite de tiempo, y avisándolo en el README. Las claves se leen de variables de entorno (`GEMINI_API_KEY`, `OPENAI_API_KEY`), nunca de archivos del repositorio.

## Diseño: «duelo editorial oscuro»
Minimalista, oscuro y tipográfico, como un informe de laboratorio.
- Fondo `#0f0f11`, texto `#e8e8ea`, líneas `#2a2a2f`.
- **Dos acentos, uno por contendiente:** A lima `#b5e853`, B rosa `#ff7eb6`. Nada más de color.
- Titulares en monoespaciada grande; cuerpo en sans del sistema.
- Gráficas de barras SVG finas, sin bordes ni leyendas recargadas.
- Legible también al imprimir (hoja de estilos de impresión clara).

## Equipo de agentes y ramas
Los tres proyectos se desarrollan en paralelo con un equipo de agentes. **Cada agente trabaja solo en su rama** y todo entra en `main` mediante pull request.

| Agente | Herramienta | Rama | Cometido |
|---|---|---|---|
| lead | Claude Code (sesión principal) | `main` (solo merges) | Plan, revisión de PRs, integración, despliegue y documentación final |
| builder | Claude Code (subagente) | `agent/builder` | Implementa el MVP, los tests básicos, el CI y el despliegue |
| qa | Claude Code (subagente) | `agent/qa` | Revisa el código, añade tests de casos límite, corrige fallos y accesibilidad |
| docs | Claude Code (subagente, Sonnet); OpenCode cuando se permita su ejecución autónoma | `agent/docs` | Guía de uso para personas usuarias en `docs/USO.md` |

## Reglas para todos los agentes
1. **Lee `MEMORY.md` antes de empezar** y **actualízalo siempre al terminar** (estado, decisiones, siguiente paso y una línea en «Registro de sesiones» con fecha, agente y rama). Una sesión sin `MEMORY.md` actualizado no está terminada.
2. Nunca hagas commit directo a `main`. Trabaja en tu rama y abre un pull request.
3. Commits convencionales en español: `feat:`, `fix:`, `test:`, `docs:`, `ci:`, `chore:`, `refactor:`. Cambios pequeños y con sentido propio.
4. No subas claves, tokens, `.env` ni datos personales. El repositorio es público.
5. No añadas dependencias sin justificarlo en «Decisiones» de `MEMORY.md`.
6. Si algo es ambiguo, elige la opción más simple, anótala en `MEMORY.md` y sigue.
7. La interfaz y la documentación, en español. El código (nombres), en inglés.

## Terminado significa
- Lint y tests en verde en local y en el CI.
- La aplicación funciona desplegada en GitHub Pages.
- README al día y `MEMORY.md` actualizado.
