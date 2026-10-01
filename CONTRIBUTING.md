# Contribuir a modelduel

Gracias por querer ayudar. Esta guía es breve; las reglas completas del equipo están en [`AGENTS.md`](AGENTS.md) y el estado del proyecto en [`MEMORY.md`](MEMORY.md). Si solo quieres **usar** modelduel, lee [`docs/USO.md`](docs/USO.md).

## Entorno

Necesitas Python 3.12 o superior.

```bash
git clone https://github.com/BertMarti/modelduel
cd modelduel
python -m venv .venv
source .venv/bin/activate        # Windows (PowerShell): .venv\Scripts\Activate.ps1
pip install -e ".[dev]"
```

El extra `dev` instala pytest, pytest-cov y ruff. En ejecución el programa solo usa la biblioteca estándar: **no añadas dependencias** sin justificarlo en «Decisiones» de `MEMORY.md`.

## Comandos

Antes de abrir un pull request tienen que pasar los mismos pasos que el CI (Ubuntu y Windows):

```bash
ruff check .                     # lint
ruff format --check .            # formato (usa «ruff format .» para aplicarlo)
pytest --cov                     # tests con cobertura; el mínimo es el 90 %
modelduel run examples/tasks --model replay:alfa --model replay:beta --model replay:gamma --out runs/demo   # demo
```

- Los tests **no pueden usar la red** ni claves reales: las APIs se simulan.
- La demo debe terminar con código 0 y generar `runs/demo/index.html` y `runs/demo/results.json`. El CI comprueba además que `--a`/`--b` sigue dando el «Informe de duelo» (la carpeta `runs/` no se sube al repositorio).
- El informe HTML y la página de clasificación no pueden contener JavaScript. El CI genera `site/leaderboard` con `modelduel leaderboard results --out site/leaderboard`.
- `results/` son datos versionados (un `results.json` por duelo o liga): añade ahí los reales con el procedimiento de [`docs/USO.md`](docs/USO.md#clasificación-pública).

## Ramas y pull requests

- **Nunca hagas commit directo a `main`.** Trabaja en una rama (`agent/<rol>/<n>-<slug>` para los agentes, con `<n>` el número del issue, por ejemplo `agent/docs/9-documentacion-v0.2`; `feat/…` o `fix/…` para personas) y abre un pull request.
- Cambios pequeños y con sentido propio. Describe qué cambia y por qué, y cómo lo has comprobado.
- Al terminar, actualiza `MEMORY.md` (estado, decisiones, siguiente paso y una línea en «Registro de sesiones»).
- La documentación y la interfaz, en español; los nombres del código, en inglés.
- No subas claves, tokens, `.env` ni datos personales: el repositorio es público.

## Commits

[Commits convencionales](https://www.conventionalcommits.org/es/) en español: `feat:`, `fix:`, `test:`, `docs:`, `ci:`, `chore:`, `refactor:`.

```text
fix: distinguir el timeout de la petición del de los tests
```

## Añadir un proveedor

Un proveedor es una clase con esta interfaz (`Provider`, en `src/modelduel/providers/base.py`):

```python
class MiProveedor:
    spec: str  # "miproveedor:<modelo>", tal como lo escribe la persona usuaria

    def complete(self, prompt: str, *, task_id: str | None = None) -> Response: ...
```

`Response` lleva `text`, `input_tokens`, `output_tokens` (pueden ser `None` si el proveedor no los da) y `latency_s`. `task_id` solo lo usa `replay`; el resto lo ignora.

1. Crea `src/modelduel/providers/<nombre>.py` (usa como modelo `gemini.py` o `openai_compat.py`). Para HTTP usa `post_json` de `base.py`, que ya convierte los fallos de red y HTTP en `ProviderError` con mensajes en español, y pásale las claves en `secrets` para que se redacten. Lee las claves **solo de variables de entorno** (`require_env`), nunca las pongas en la URL ni en los mensajes de error.
2. Registra el proveedor en `src/modelduel/providers/__init__.py`: añade su nombre a `PROVIDERS` y una rama en `get_provider`.
3. Si tiene precios propios o variables nuevas, documéntalo en el README (tabla «Proveedores y variables de entorno») y en `docs/USO.md`.
4. Escribe los tests en `tests/test_providers.py` **sin red**: simula `urllib.request.urlopen` con el ayudante `_fake_urlopen` del propio archivo y prueba la respuesta buena, la falta de clave, las respuestas vacías o raras y los errores HTTP (401, 429, 5xx).

Toda excepción de un proveedor debe ser `ProviderError`: el duelo la registra como «error del proveedor» y sigue con el resto de intentos.

## Añadir una tarea de ejemplo

Una tarea es una carpeta en `examples/tasks/<id>/` con `task.md`, `test_task.py` y `meta.toml` (formato en el README y en [`docs/USO.md`](docs/USO.md#crear-tu-propia-tarea-paso-a-paso)). Las tareas de ejemplo son **originales**: no copies enunciados ni tests de otras fuentes.

1. Crea los tres archivos. Incluye casos límite y da un `order` y una `difficulty` coherentes con las demás.
2. Graba una respuesta por contendiente en `examples/replays/alfa/<id>.md` y `examples/replays/beta/<id>.md` (con el front-matter de tokens y latencia). Son ficticias y se escriben a mano.
3. Actualiza lo que dependa del conjunto de tareas: `tests/test_tasks.py` (orden esperado) y `tests/test_cli.py` (resultados de la demo), además de las cifras del README y de la web (`site/index.html`) si cambian los marcadores.
4. Comprueba `modelduel list-tasks examples/tasks`, ejecuta la demo y revisa el informe.

## Añadir un color a la paleta de la liga

La liga admite hasta seis contendientes (`A` a `F`), cada uno con un acento. Para subir el máximo y añadir un séptimo (`G`), hay que tocar estos sitios:

1. **Letra:** añade `"g"` a `ALL_SIDES` en `src/modelduel/results.py` (`MAX_CONTENDERS` se calcula solo).
2. **Color:** en `src/modelduel/report/style.css` añade `--g` en `:root`, las reglas `.g { color: var(--g); }` y `.fill-g { fill: var(--g); }`, y el valor para la hoja de impresión en el `:root` de `@media print`.
3. **Elige un color que pase el contraste AA** (mínimo 4,5:1): en pantalla, sobre el fondo `#0f0f11` y sobre el panel `#151518`; en impresión, sobre blanco y sobre el panel claro `#f6f6f6`. Además, el valor «perdedor» atenuado (`opacity: .8`) sigue teniendo que llegar a 4,5:1, y el color tiene que distinguirse de los demás (con la letra siempre al lado: el color nunca es la única pista).
4. **Tests:** `tests/test_league.py` calcula el contraste de toda la paleta (`test_paleta_ampliada_cumple_contraste_aa` y `test_contraste_aa_de_toda_la_paleta_sobre_todos_fondos`) y exige colores distintos: si tu color no cumple, fallan. Varios tests fijan «6» a mano (`_html(make_task, 6)`, «máximo 6», `len(...) == 6`): actualízalos a 7. Ejecuta `pytest tests/test_league.py tests/test_report.py`.
5. **Documentación:** la paleta aparece en `AGENTS.md` (sección «Diseño»), `docs/USO.md` y el README (límite de seis), y en la web (`site/index.html`).

## Publicar una versión en PyPI (mantenedor)

La publicación es automática y **no usa tokens**: `release.yml` usa *Trusted Publishing* (OIDC) de PyPI, a través del *environment* de GitHub `pypi`.

**Una sola vez (configuración previa):**

1. En PyPI: *Your projects* > *Publishing* > *Add a new pending publisher*, con proyecto `modelduel`, propietario `BertMarti`, repositorio `modelduel`, workflow `release.yml` y environment `pypi`.
2. En GitHub: *Settings* > *Environments* > crea el environment `pypi` (puedes añadirle revisores obligatorios para aprobar cada publicación).

**En cada versión:**

1. Sube la versión en `src/modelduel/__init__.py` (única fuente: `pyproject.toml` la lee de ahí), pasa la sección «Sin publicar» de `CHANGELOG.md` a la nueva versión con su fecha (y actualiza los enlaces de comparación del final), actualiza `MEMORY.md` y fusiona el PR en `main`.
2. Crea una *Release* en GitHub sobre un commit de `main`, con una etiqueta `vX.Y.Z` igual a la versión (por ejemplo, `v0.2.0`).
3. El workflow construye el sdist y la wheel, comprueba que el commit está en `main` y que la etiqueta coincide con la versión, ejecuta `twine check --strict`, prueba la wheel en un entorno limpio y, si todo va bien, publica en PyPI a través del *environment* `pypi`. Sigue el resultado en la pestaña *Actions*.
4. Comprueba la publicación desde un entorno limpio: `pip install "modelduel[pytest]"` y `modelduel demo`.

Para comprobar el paquete en local sin publicar: `pip install build twine`, `python -m build` y `twine check dist/*`.
