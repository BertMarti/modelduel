@AGENTS.md
@MEMORY.md

## Claude Code
- **Subagentes:** Usa los definidos en `.claude/agents/` para revisiones de seguridad y pruebas web.
- **Skills:** Consulta `.claude/skills/` para tareas repetitivas (añadir tareas, publicar versiones).
- **Hoja de ruta:** El plan de desarrollo activo reside en `PLAN.md`.
- **Seguridad:** NUNCA ejecutes código de modelos fuera de `run_tests`. Prohibido incluir claves en `results.json` o informes.
- **Calidad (CI):** Antes de PR, verifica:
  - `ruff check . && ruff format --check .`
  - `mypy`
  - `pytest --cov`
  - `node --test "tests/js/*.test.cjs"`
