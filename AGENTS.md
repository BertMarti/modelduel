# AGENTS.md · modelduel

## Qué es
CLI que enfrenta a dos modelos de IA (o a una liga de hasta seis) con la misma tarea de programación: les pide el código, ejecuta los tests de la tarea sobre cada respuesta y genera un informe HTML con aciertos, tiempo, tokens y coste estimado. Convierte en herramienta el ejercicio «tu propia comparativa» de la guía de modelos del curso.

## Tecnología (propia de este proyecto)
- **Python 3.12**, paquete instalable con `pyproject.toml` (backend `hatchling`).
- Solo biblioteca estándar en tiempo de ejecución (HTTP con `urllib`, CLI con `argparse`). Informe HTML con plantilla propia (`string.Template`) y **gráficas SVG en línea**, sin JavaScript.
- **pytest** para tests; **ruff** para lint y formato.
- Despliegue: **GitHub Pages** con la web del proyecto y un **informe de demostración** generado en el CI con respuestas grabadas (proveedor `replay`), sin claves.

## Comandos
- Entorno: `python -m venv .venv` y `pip install -e ".[dev]"`
- Lint: `ruff check . && ruff format --check .`
- Tests: `pytest`
- Clasificación: `modelduel leaderboard results --out site/leaderboard`
- JS: `node --test "tests/js/*.test.cjs"` (solo `site/demo.js`; Node no es dependencia del paquete)
- Demo: `modelduel run examples/tasks --model replay:alfa --model replay:beta --model replay:gamma --out site/demo`

## Estructura
- `src/modelduel/cli.py` punto de entrada.
- `src/modelduel/providers/` proveedores: `replay` (grabado), `gemini` (API de Google), `openai` (cualquier API compatible con OpenAI: OpenRouter, Ollama…), `omniroute` (preset de `openai` para el router local OmniRoute).
- `src/modelduel/runner.py` extrae el código de la respuesta y ejecuta los tests en un directorio temporal con límite de tiempo.
- `src/modelduel/report/` informe HTML: duelo de dos (`html.py`, `template.html`) y liga de 3 a 6 (`league.py`, `league.html`); el CSS común está en `style.css`.
- `src/modelduel/leaderboard.py` clasificación pública: agrega `results/*.json` por modelo (por proporciones) y genera `site/leaderboard` (plantilla `report/leaderboard.html`); orden `modelduel leaderboard`.
- `results/` resultados versionados (un `results.json` por duelo o liga; siembra: tres de `replay`).
- `src/modelduel/resume.py` reanudación de duelos cortados (`--resume`).
- `examples/tasks/` tareas de ejemplo originales (enunciado + tests) y `examples/replays/` respuestas grabadas.
- `site/` web estática del proyecto: `index.html` (portada con la sección `#demo`) y `demo.js` (el duelo en directo). `tests/js/` tiene las pruebas de su lógica (`node --test`).

## Seguridad
El código generado por un modelo se ejecuta en local: siempre en un directorio temporal, en un subproceso con límite de tiempo, y avisándolo en el README. Las claves se leen de variables de entorno (`GEMINI_API_KEY`, `OPENAI_API_KEY`), nunca de archivos del repositorio.

## Diseño: «duelo editorial oscuro»
Minimalista, oscuro y tipográfico, como un informe de laboratorio.
- Fondo `#0f0f11`, texto `#e8e8ea`, líneas `#2a2a2f`.
- **Un acento por contendiente:** A lima `#b5e853`, B rosa `#ff7eb6`. En una liga (hasta 6) se amplía con C cian `#4fd1e5`, D ámbar `#ffb833`, E violeta `#b79cff` y F coral `#ff8a65`, todos con contraste AA sobre el fondo, y siempre acompañados de su letra. Nada más de color.
- Titulares en monoespaciada grande; cuerpo en sans del sistema.
- Gráficas de barras SVG finas, sin bordes ni leyendas recargadas.
- Legible también al imprimir (hoja de estilos de impresión clara).

### Duelo en directo (`site/demo.js`, desde v0.5.0)
Reproduce en la portada un duelo **pregrabado**: `fetch("demo/results.json")` solo al pulsar «Ver un duelo en directo», primera tarea del duelo, sin servidor, claves ni ejecución real; siempre rotulado «resultado pregrabado».
- Es el **único `<script>`** de la web (`<script src="demo.js" defer>`); los informes y `site/leaderboard` siguen sin JavaScript (el CI lo comprueba).
- Vanilla y mínimo. El código grabado es dato no fiable: se escribe **solo con `textContent`**, nunca `innerHTML` (un test lo prohíbe). Los datos se validan (`prepare`) y se acotan (6 contendientes, 200 tests, 4000 caracteres).
- Línea de tiempo de ~25 s en función del tiempo transcurrido: 0-3 s enunciado, 3-12 s escritura (∝ latencia), 12-20 s tests con ✓/✗/– y texto, 20-25 s marcador. La lógica pura (`phaseAt`, `typedLength`, `testMarks`, `verdict`…) se exporta y se prueba con `node --test`.
- Accesibilidad: sin autoarranque; el botón principal conserva el foco (Pausar/Reanudar/Siguiente/Ver otra vez) y «Detener» aparece mientras hay duelo; `visibilitychange` pausa; con `prefers-reduced-motion` no hay animación y se avanza con «Siguiente»; `aria-live="polite"` solo anuncia el cambio de fase y el veredicto; sin JS queda un enlace al informe estático.

### Ajustes visuales de v0.5.0 (siguen siendo «duelo editorial oscuro»)
- Enlaces con subrayado `--muted` y `:focus-visible` en informes y portada; nada por debajo de 12 px.
- El «peor» se marca con «▼ peor» y el mejor con «▲ mejor» (glifo + texto); prohibido atenuar con `opacity` (es información por color).
- Portada: una sola acción primaria («Ver un duelo en directo»), navegación corta, sin barras decorativas con datos copiados a mano; los datos reales se enseñan en el duelo en directo.
- Tablas desplazables como `tabindex="0" role="region" aria-label` con foco visible; pie de los informes con enlace a la web.

## Equipo de agentes y ramas
Desde v0.2.0 el trabajo va **guiado por issues del hito** y cada issue lleva la etiqueta del agente responsable (`agent:builder`, `agent:qa`, `agent:docs`). Todo entra en `main` mediante pull request.

| Agente | Herramienta | Etiqueta | Cometido |
|---|---|---|---|
| lead | Claude Code (sesión principal) | (crea y prioriza los issues) | Plan, revisión de PRs, integración, despliegue y documentación final |
| builder | Claude Code (subagente) | `agent:builder` | Implementa funciones, el CI y el despliegue |
| qa | Claude Code (subagente) | `agent:qa` | Revisa el código, añade tests de casos límite, corrige fallos y accesibilidad |
| docs | Claude Code (subagente, Sonnet); OpenCode cuando se permita su ejecución autónoma | `agent:docs` | Guía de uso para personas usuarias en `docs/USO.md` y documentación |

Flujo de trabajo:
1. Un agente toma los issues de su etiqueta en el hito activo (`gh issue list --milestone <hito> --label agent:<rol>`); sus criterios de aceptación son el contrato.
2. **Una rama y un PR por issue**, con rama `agent/<rol>/<n>-<slug>` (por ejemplo `agent/builder/4-reintentos`). Si un issue depende del anterior, la rama parte de la anterior.
3. **Todos los PR van contra `main`** (nunca contra otra rama de agente) y su descripción incluye `Closes #<n>`, qué cambia, cómo se verificó y, si depende de otro PR, «Se fusiona después de #<PR>».
4. **Alberto fusiona** los PR (`main` está protegida): ningún agente hace commit ni push a `main` ni fusiona PRs.
5. Cada commit termina con una línea en blanco y las líneas `Agente: <rol> (<herramienta>)` y `Co-Authored-By`.

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
