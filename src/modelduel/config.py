"""Configuración ``modelduel.toml`` y carpeta inicial (``modelduel init``).

Las claves de las APIs NUNCA van en la configuración: se leen de variables de entorno.
"""

from __future__ import annotations

import shutil
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from modelduel.demo import examples_dir
from modelduel.results import MAX_CONTENDERS, MIN_CONTENDERS
from modelduel.sandbox import SANDBOX_CHOICES

CONFIG_NAME = "modelduel.toml"
PLACEHOLDER = "CAMBIA-ESTO"


@dataclass(frozen=True)
class ProviderInfo:
    """Lo que necesita cada proveedor que ofrece ``modelduel init``."""

    prefix: str  # prefijo de la especificación proveedor:modelo
    key_env: str  # variable con la clave ("" si no hace falta)
    key_url: str  # dónde se consigue la clave
    models_hint: str  # dónde se mira la lista de modelos
    extra_env: tuple[tuple[str, str], ...] = ()  # otras variables (nombre, valor de ejemplo)
    note: str = ""


PROVIDER_CATALOG: dict[str, ProviderInfo] = {
    "gemini": ProviderInfo(
        prefix="gemini",
        key_env="GEMINI_API_KEY",
        key_url="https://aistudio.google.com/apikey",
        models_hint="https://ai.google.dev/gemini-api/docs/models",
    ),
    "openai": ProviderInfo(
        prefix="openai",
        key_env="OPENAI_API_KEY",
        key_url="https://platform.openai.com/api-keys",
        models_hint="https://platform.openai.com/docs/models",
    ),
    "openrouter": ProviderInfo(
        prefix="openai",
        key_env="OPENAI_API_KEY",
        key_url="https://openrouter.ai/keys",
        models_hint="https://openrouter.ai/models",
        extra_env=(("OPENAI_BASE_URL", "https://openrouter.ai/api/v1"),),
        note="OPENAI_API_KEY lleva aquí la clave de OpenRouter",
    ),
    "ollama": ProviderInfo(
        prefix="openai",
        key_env="",
        key_url="",
        models_hint="la orden `ollama list`",
        extra_env=(("OPENAI_BASE_URL", "http://localhost:11434/v1"),),
        note="sin clave; Ollama tiene que estar en marcha",
    ),
    "omniroute": ProviderInfo(
        prefix="omniroute",
        key_env="",
        key_url="",
        models_hint="el panel de tu OmniRoute",
        extra_env=(("OMNIROUTE_BASE_URL", "http://localhost:20128/v1"),),
        note="añade OMNIROUTE_API_KEY solo si tu instalación la pide",
    ),
}
# Para el mensaje del marcador: dónde se miran los modelos según el prefijo de la especificación.
MODELS_HINT_BY_PREFIX = {
    "gemini": PROVIDER_CATALOG["gemini"].models_hint,
    "openai": PROVIDER_CATALOG["openai"].models_hint,
    "omniroute": PROVIDER_CATALOG["omniroute"].models_hint,
}
# Proveedores que comparten OPENAI_BASE_URL/OPENAI_API_KEY: solo uno por duelo.
_SHARED_OPENAI = ("openai", "openrouter", "ollama")

VALID_KEYS = (
    "tareas",
    "modelos",
    "ejecuciones",
    "tiempo_limite",
    "salida",
    "formato",
    "aislamiento",
)


class ConfigError(Exception):
    """Configuración no válida o carpeta inicial imposible de crear."""


@dataclass(frozen=True)
class Config:
    path: Path
    tasks: Path
    models: list[str]
    runs: int | None = None
    timeout: float | None = None
    out: Path | None = None
    format: str | None = None
    sandbox: str | None = None  # «aislamiento»: auto, docker, podman o ninguno


def find_config(explicit: Path | None) -> Path | None:
    """``--config`` si se da; si no, ``modelduel.toml`` del directorio actual si existe."""
    if explicit is not None:
        return explicit
    default = Path(CONFIG_NAME)
    return default if default.is_file() else None


def load_config(path: Path) -> Config:
    """Lee y valida ``path``. Las rutas relativas lo son a la carpeta del archivo."""
    try:
        text = path.read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ConfigError(
            f"no existe {path}. Crea una configuración con `modelduel init`."
        ) from None
    except OSError as exc:
        raise ConfigError(f"no se pudo leer {path}: {exc.strerror or exc}.") from None
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ConfigError(f"{path} no es un TOML válido: {exc}.") from None

    unknown = sorted(set(data) - set(VALID_KEYS))
    if unknown:
        raise ConfigError(
            f"{path}: clave desconocida «{unknown[0]}». Las válidas son: {', '.join(VALID_KEYS)}."
        )
    for key in ("tareas", "modelos"):
        if key not in data:
            raise ConfigError(f"{path}: falta «{key}».")
    tasks = _typed(path, data, "tareas", str, "un texto (carpeta de tareas)")
    models = _typed(path, data, "modelos", list, "una lista de textos proveedor:modelo")
    if not all(isinstance(m, str) and m.strip() for m in models):
        raise ConfigError(f"{path}: «modelos» debe ser una lista de textos proveedor:modelo.")
    if not MIN_CONTENDERS <= len(models) <= MAX_CONTENDERS:
        raise ConfigError(
            f"{path}: «modelos» necesita de {MIN_CONTENDERS} a {MAX_CONTENDERS} contendientes "
            f"(tiene {len(models)})."
        )
    runs = _typed(path, data, "ejecuciones", int, "un número entero")
    if runs is not None and runs < 1:
        raise ConfigError(f"{path}: «ejecuciones» debe ser 1 o más.")
    timeout = _typed(path, data, "tiempo_limite", (int, float), "un número de segundos")
    if timeout is not None and not 0 < timeout < float("inf"):
        raise ConfigError(f"{path}: «tiempo_limite» debe ser un número de segundos mayor que 0.")
    out = _typed(path, data, "salida", str, "un texto (carpeta de resultados)")
    fmt = _typed(path, data, "formato", str, "un texto: html, md o html,md")
    sandbox = _typed(path, data, "aislamiento", str, f"uno de: {', '.join(SANDBOX_CHOICES)}")
    if sandbox is not None:
        sandbox = sandbox.strip().lower()
        if sandbox not in SANDBOX_CHOICES:
            raise ConfigError(
                f"{path}: «aislamiento» debe ser uno de: {', '.join(SANDBOX_CHOICES)} "
                f"(tiene «{sandbox}»)."
            )
    base = path.parent
    return Config(
        path=path,
        tasks=base / tasks,
        models=[m.strip() for m in models],
        runs=runs,
        timeout=float(timeout) if timeout is not None else None,
        out=base / out if out else None,
        format=fmt,
        sandbox=sandbox,
    )


def _typed(path: Path, data: dict, key: str, kind: type | tuple[type, ...], what: str) -> Any:
    value = data.get(key)
    # En TOML true/false son bool, que en Python también es int: no se aceptan como número.
    if value is not None and (not isinstance(value, kind) or isinstance(value, bool)):
        raise ConfigError(f"{path}: «{key}» debe ser {what}.")
    return value


def placeholder_error(spec: str, config_path: Path | None) -> str | None:
    """Mensaje guía si ``spec`` aún lleva el marcador de ``modelduel init``."""
    if PLACEHOLDER not in spec:
        return None
    prefix = spec.partition(":")[0].strip().lower()
    hint = MODELS_HINT_BY_PREFIX.get(prefix, "la documentación de tu proveedor")
    where = f"edita {config_path}: " if config_path else ""
    return f"{where}cambia «{spec}» por un modelo real (lista de modelos: {hint})."


def safe_url(url: str) -> str:
    """URL para mostrar: sin usuario ni contraseña y sin la consulta ni el fragmento.

    Una clave puede ir en ``user:pass@`` o en ``?token=…``; de la consulta solo se dice que hay.
    """
    try:
        parts = urlsplit(url)
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
    except ValueError:
        return "(URL no válida)"
    if not parts.scheme or not host:
        return "(URL no válida)"
    shown = f"{parts.scheme}://{host}{parts.path}"
    if parts.query or parts.fragment:
        shown += "?…"
    return shown


def init_specs(selected: list[str]) -> list[str]:
    """Contendientes iniciales: grabados sin proveedores, marcadores con ellos."""
    chosen = list(dict.fromkeys(selected))
    if not chosen:
        return ["replay:alfa", "replay:beta"]
    shared = [name for name in chosen if name in _SHARED_OPENAI]
    if len(shared) > 1:
        raise ConfigError(
            f"{' y '.join(shared)} comparten OPENAI_BASE_URL y OPENAI_API_KEY: en un mismo duelo "
            "solo puede ir uno. Para mezclar modelos de varias empresas usa openrouter u omniroute."
        )
    prefixes = [PROVIDER_CATALOG[name].prefix for name in chosen]
    if len(prefixes) == 1:
        return [f"{prefixes[0]}:{PLACEHOLDER}-1", f"{prefixes[0]}:{PLACEHOLDER}-2"]
    return [f"{prefix}:{PLACEHOLDER}" for prefix in prefixes]


def env_lines(name: str) -> list[str]:
    """Variables que pide un proveedor, como líneas «VARIABLE=valor de ejemplo»."""
    info = PROVIDER_CATALOG[name]
    lines = [f"{env}={example}" for env, example in info.extra_env]
    if info.key_env:
        lines.insert(0, f"{info.key_env}=PEGA_AQUI_TU_CLAVE")
    return lines


def render_config(specs: list[str], providers: list[str]) -> str:
    """Texto de ``modelduel.toml`` comentado en español."""
    models = ", ".join(f'"{spec}"' for spec in specs)
    lines = [
        "# Configuración de modelduel (creada con `modelduel init`).",
        "# `modelduel run` sin argumentos usa estos valores; las opciones de la orden mandan.",
        "# Las claves de las APIs NUNCA van aquí: se leen de variables de entorno.",
        "# Comprueba que todo está listo con: modelduel doctor",
        "",
        "# Carpeta de tareas (cada tarea: task.md con el enunciado y test_task.py con los tests).",
        'tareas = "tasks"',
        "",
        "# Contendientes: de 2 a 6, como proveedor:modelo.",
    ]
    if any(PLACEHOLDER in spec for spec in specs):
        lines.append(f"# Cambia {PLACEHOLDER} por el nombre exacto del modelo.")
    else:
        lines.append(
            "# replay:alfa y replay:beta son respuestas grabadas: funcionan sin claves ni coste."
        )
    lines += [
        f"modelos = [{models}]",
        "",
        "# Ejecuciones por tarea (con modelos reales, 3 o más dan una señal más fiable).",
        "ejecuciones = 1",
        "",
        "# Carpeta donde se guardan results.json y el informe.",
        'salida = "resultados"',
        "",
        "# Formato del informe: html, md o html,md.",
        'formato = "html"',
        "",
        "# Segundos máximos para los tests de cada respuesta (20 por defecto).",
        "# tiempo_limite = 20",
        "",
        "# Dónde se ejecuta el código de los modelos: auto (en local; en Linux, sin red si se",
        "# puede), docker o podman (contenedor sin red ni privilegios: lo más seguro) o ninguno.",
        '# aislamiento = "docker"',
    ]
    for name in providers:
        info = PROVIDER_CATALOG[name]
        lines += ["", f"# {name}: variables de entorno que necesita"]
        lines += [f"#   {line}" for line in env_lines(name)]
        if info.note:
            lines.append(f"#   ({info.note})")
        if info.key_url:
            lines.append(f"#   clave: {info.key_url}")
        lines.append(f"#   modelos: {info.models_hint}")
    return "\n".join(lines) + "\n"


def init_project(target: Path, providers: list[str]) -> list[str]:
    """Crea ``target`` con ``tasks/``, ``replays/`` y ``modelduel.toml``; nunca sobrescribe."""
    providers = list(dict.fromkeys(providers))
    specs = init_specs(providers)
    config_path = target / CONFIG_NAME
    if config_path.exists():
        raise ConfigError(
            f"{config_path} ya existe: no se sobrescribe. Edítalo o elige otra carpeta."
        )
    for name in ("tasks", "replays"):
        if (target / name).exists():
            raise ConfigError(
                f"{target / name} ya existe: no se machacan tus tareas. Elige otra carpeta."
            )
    examples = examples_dir()
    ignore = shutil.ignore_patterns("__pycache__")
    try:
        target.mkdir(parents=True, exist_ok=True)
        shutil.copytree(examples / "tasks", target / "tasks", ignore=ignore)
        shutil.copytree(examples / "replays", target / "replays", ignore=ignore)
        config_path.write_text(render_config(specs, providers), encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"no se pudo crear {target}: {exc.strerror or exc}.") from None
    return specs
