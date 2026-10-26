"""``modelduel doctor``: comprueba la instalación, las claves y la configuración.

Nunca muestra el valor de una clave (ni parte de ella). Solo sale a la red con ``--red``, y
entonces solo pide la lista de modelos de cada proveedor, que no gasta tokens.
"""

from __future__ import annotations

import importlib.metadata
import importlib.util
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from modelduel import __version__
from modelduel.config import (
    Config,
    ConfigError,
    find_config,
    load_config,
    placeholder_error,
    safe_url,
)
from modelduel.demo import examples_dir
from modelduel.providers import ProviderError, parse_spec
from modelduel.providers.base import USER_AGENT, http_timeout, redact
from modelduel.providers.gemini import DEFAULT_BASE_URL as GEMINI_URL
from modelduel.providers.openai_compat import DEFAULT_BASE_URL as OPENAI_URL
from modelduel.providers.openai_compat import OmniRouteProvider
from modelduel.runner import isolation_summary, supervisor_supported
from modelduel.sandbox import (
    available_container_tools,
    network_isolation_available,
    network_isolation_hint,
)
from modelduel.tasks import TaskError, discover_tasks

OK, FAIL, WARN, INFO = "✓", "✗", "!", "·"
NETWORK_TIMEOUT = 10.0
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}
KEY_VARS = ("GEMINI_API_KEY", "OPENAI_API_KEY", "OMNIROUTE_API_KEY")
URL_VARS = ("GEMINI_BASE_URL", "OPENAI_BASE_URL", "OMNIROUTE_BASE_URL")

# (url, cabeceras, límite en s) -> código HTTP. Lanza OSError si no hay conexión.
Request = Callable[[str, dict[str, str], float], int]


@dataclass(frozen=True)
class Check:
    status: str  # OK, FAIL, WARN o INFO
    text: str
    group: str


def _defined(env: Mapping[str, str], name: str) -> bool:
    return bool(env.get(name, "").strip())


def _is_local(url: str) -> bool:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower() in LOCAL_HOSTS
    except ValueError:
        return False


def _export(name: str, value: str = "PEGA_AQUI_TU_CLAVE") -> str:
    return f'export {name}="{value}"'


# ---------------------------------------------------------------- comprobaciones


def install_checks() -> list[Check]:
    group = "Instalación"
    python = sys.version.split()[0]
    checks = [
        Check(OK, f"Python {python}", group)
        if sys.version_info >= (3, 12)
        else Check(FAIL, f"Python {python}: modelduel necesita 3.12 o más nuevo", group),
        Check(OK, f"modelduel {__version__}", group),
    ]
    if importlib.util.find_spec("pytest") is None:
        checks.append(
            Check(
                FAIL,
                "falta pytest (hace falta para ejecutar los tests). Instálalo con: "
                f'"{sys.executable}" -m pip install pytest',
                group,
            )
        )
    else:
        try:
            version = importlib.metadata.version("pytest")
        except importlib.metadata.PackageNotFoundError:
            version = "(versión desconocida)"
        checks.append(Check(OK, f"pytest {version}", group))
    try:
        examples_dir()
        checks.append(
            Check(OK, "ejemplos incluidos: prueba sin claves con `modelduel demo`", group)
        )
    except TaskError as exc:
        checks.append(Check(FAIL, str(exc), group))
    return checks


def protection_checks() -> list[Check]:
    group = "Protección al ejecutar el código de los modelos"
    return [Check(INFO, item, group) for item in isolation_summary()]


def isolation_checks(
    tools: list[str] | None = None,
    netns: bool | None = None,
    config: Config | None = None,
) -> list[Check]:
    """Qué aislamiento hay disponible (contenedor, red cortada o nada) y cuál conviene.

    Solo mira el PATH y prueba los espacios de nombres en un proceso aparte: no arranca
    contenedores ni habla con el demonio de Docker.
    """
    group = "Aislamiento disponible"
    tools = available_container_tools() if tools is None else tools
    if netns is None:
        netns = network_isolation_available() and supervisor_supported()
    checks = []
    for tool in tools:
        checks.append(
            Check(
                OK, f"{tool} instalado: --sandbox {tool} ejecuta los tests en un contenedor", group
            )
        )
    if not tools:
        checks.append(
            Check(INFO, "ni Docker ni Podman en el PATH (contenedor no disponible)", group)
        )
    if netns:
        checks.append(
            Check(OK, "red cortada por defecto (espacio de nombres de red, sin root)", group)
        )
    else:
        checks.append(Check(WARN, network_isolation_hint(), group))
    if tools:
        best = f"recomendado para código no fiable: --sandbox {tools[0]}"
        best += " (o «aislamiento» en modelduel.toml)"
    elif netns:
        best = (
            "recomendado: el modo por defecto ya corta la red; para un aislamiento completo "
            "(disco, memoria, procesos) instala Docker o Podman y usa --sandbox docker"
        )
    else:
        best = (
            "recomendado: instala Docker o Podman y usa --sandbox docker, o genera con "
            "--solo-generar y ejecuta los tests en otra máquina con --replay"
        )
    checks.append(Check(INFO, best, group))
    wanted = config.sandbox if config is not None else None
    if wanted in ("docker", "podman") and wanted not in tools:
        checks.append(
            Check(
                FAIL,
                f'modelduel.toml pide aislamiento = "{wanted}", pero {wanted} no está instalado',
                group,
            )
        )
    return checks


def env_checks(env: Mapping[str, str]) -> list[Check]:
    group = "Variables de entorno"
    checks = []
    for name in KEY_VARS:
        value = env.get(name, "")
        if not value.strip():
            checks.append(Check(INFO, f"{name}: no definida", group))
        elif value != value.strip() or value[:1] in "\"'" or value[-1:] in "\"'":
            checks.append(
                Check(
                    WARN, f"{name}: definida, pero parece llevar comillas o espacios de más", group
                )
            )
        else:
            checks.append(Check(OK, f"{name}: definida (no se muestra)", group))
    for name in URL_VARS:
        if _defined(env, name):
            shown = redact(safe_url(env[name].strip()), tuple(env.get(k, "") for k in KEY_VARS))
            checks.append(Check(OK, f"{name}: {shown}", group))
        else:
            checks.append(Check(INFO, f"{name}: no definida (se usa la de por defecto)", group))
    if _defined(env, "MODELDUEL_HTTP_TIMEOUT"):
        try:
            checks.append(Check(OK, f"MODELDUEL_HTTP_TIMEOUT: {http_timeout(env):g} s", group))
        except ProviderError as exc:
            checks.append(Check(FAIL, str(exc), group))
    return checks


def requirement_check(spec: str, env: Mapping[str, str]) -> Check:
    """¿Tiene ``spec`` lo que necesita para funcionar? (sin red)."""
    group = "Configuración"
    try:
        kind, _model = parse_spec(spec)
    except ProviderError as exc:
        return Check(FAIL, str(exc), group)
    if kind == "gemini" and not _defined(env, "GEMINI_API_KEY"):
        return Check(FAIL, f"{spec} necesita GEMINI_API_KEY: {_export('GEMINI_API_KEY')}", group)
    if kind == "openai":
        base = env.get("OPENAI_BASE_URL", "").strip() or OPENAI_URL
        if not _is_local(base) and not _defined(env, "OPENAI_API_KEY"):
            return Check(
                FAIL,
                f"{spec} necesita OPENAI_API_KEY para {safe_url(base)}: "
                f"{_export('OPENAI_API_KEY')}",
                group,
            )
    if kind == "replay":
        return Check(OK, f"{spec}: respuestas grabadas, sin clave", group)
    return Check(OK, f"{spec}: listo", group)


def config_checks(path: Path | None, env: Mapping[str, str]) -> tuple[list[Check], Config | None]:
    group = "Configuración"
    if path is None:
        return [
            Check(INFO, "no hay modelduel.toml aquí (opcional: créalo con `modelduel init`)", group)
        ], None
    try:
        config = load_config(path)
    except ConfigError as exc:
        return [Check(FAIL, str(exc), group)], None
    checks = [Check(OK, f"{path} es válido", group)]
    for spec in config.models:
        problem = placeholder_error(spec, config.path)
        checks.append(Check(FAIL, problem, group) if problem else requirement_check(spec, env))
    try:
        tasks = discover_tasks(config.tasks)
        checks.append(Check(OK, f"{len(tasks)} tareas en {config.tasks}", group))
    except TaskError as exc:
        checks.append(Check(FAIL, str(exc), group))
    except OSError as exc:
        checks.append(Check(FAIL, f"no se pudo leer {config.tasks}: {exc.strerror or exc}", group))
    return checks, config


# ---------------------------------------------------------------- red


def http_get_status(url: str, headers: dict[str, str], timeout: float) -> int:
    """GET y código HTTP (también los de error). Lanza ``OSError`` si no hay conexión."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **headers})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:
            return int(resp.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)


def _endpoint(kind: str, env: Mapping[str, str]) -> tuple[str, dict[str, str], str]:
    """(URL de la lista de modelos, cabeceras, clave) de un proveedor."""
    if kind == "gemini":
        base = env.get("GEMINI_BASE_URL", "").strip() or GEMINI_URL
        key = env.get("GEMINI_API_KEY", "").strip()
        return f"{base.rstrip('/')}/models", {"x-goog-api-key": key}, key
    if kind == "omniroute":
        base = env.get("OMNIROUTE_BASE_URL", "").strip() or OmniRouteProvider.DEFAULT_BASE_URL
        key = env.get("OMNIROUTE_API_KEY", "").strip()
    else:
        base = env.get("OPENAI_BASE_URL", "").strip() or OPENAI_URL
        key = env.get("OPENAI_API_KEY", "").strip()
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    return f"{base.rstrip('/')}/models", headers, key


_STATUS_HINTS = {
    400: "petición rechazada (Gemini responde así a una clave no válida)",
    401: "la clave no es válida",
    403: "la clave no tiene permiso",
    404: "¿es correcta la URL base?",
    429: "límite de peticiones o cuota agotada",
}


def network_checks(kinds: list[str], env: Mapping[str, str], request: Request) -> list[Check]:
    group = "Red (lista de modelos; no gasta tokens)"
    checks = []
    for kind in dict.fromkeys(kinds):
        if kind == "replay":
            continue
        url, headers, key = _endpoint(kind, env)
        shown = safe_url(url)
        if kind == "gemini" and not key:
            checks.append(Check(WARN, f"{kind}: se omite, falta GEMINI_API_KEY", group))
            continue
        try:
            status = request(url, headers, NETWORK_TIMEOUT)
        except TimeoutError:
            checks.append(
                Check(FAIL, f"{kind}: {shown} no respondió en {NETWORK_TIMEOUT:g} s", group)
            )
            continue
        except (OSError, ValueError) as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError):
                text = f"{kind}: {shown} no respondió en {NETWORK_TIMEOUT:g} s"
            else:
                text = redact(
                    f"{kind}: no se pudo conectar con {shown} ({reason}); "
                    "¿está en marcha el servicio y es correcta la URL?",
                    (key,),
                )
            checks.append(Check(FAIL, text, group))
            continue
        if 200 <= status < 300:
            checks.append(Check(OK, f"{kind}: {shown} responde (HTTP {status})", group))
        else:
            hint = _STATUS_HINTS.get(status) or ("error del servidor" if status >= 500 else "")
            hint = f": {hint}" if hint else ""
            checks.append(Check(FAIL, f"{kind}: {shown} devolvió HTTP {status}{hint}", group))
    if not checks:
        checks.append(Check(INFO, "no hay proveedores reales que comprobar", group))
    return checks


def _kinds_to_probe(config: Config | None, env: Mapping[str, str]) -> list[str]:
    if config is not None:
        kinds = []
        for spec in config.models:
            try:
                kinds.append(parse_spec(spec)[0])
            except ProviderError:
                continue
        return kinds
    kinds = []
    if _defined(env, "GEMINI_API_KEY"):
        kinds.append("gemini")
    if _defined(env, "OPENAI_API_KEY") or _defined(env, "OPENAI_BASE_URL"):
        kinds.append("openai")
    if _defined(env, "OMNIROUTE_API_KEY") or _defined(env, "OMNIROUTE_BASE_URL"):
        kinds.append("omniroute")
    return kinds


# ---------------------------------------------------------------- conjunto


def collect_checks(
    config_path: Path | None = None,
    network: bool = False,
    env: Mapping[str, str] | None = None,
    request: Request | None = None,
) -> list[Check]:
    env = os.environ if env is None else env
    found, config = config_checks(find_config(config_path), env)
    checks = install_checks() + protection_checks() + isolation_checks(config=config)
    checks += env_checks(env) + found
    if network:
        checks += network_checks(_kinds_to_probe(config, env), env, request or http_get_status)
    else:
        checks.append(
            Check(INFO, "conectividad no comprobada: añade --red (no gasta tokens)", "Red")
        )
    return checks


def render(checks: list[Check], config_found: bool = False) -> tuple[str, int]:
    """Texto para la terminal y código de salida (0 sin fallos, 1 con alguno)."""
    lines: list[str] = []
    group = None
    for check in checks:
        if check.group != group:
            group = check.group
            if lines:
                lines.append("")
            lines.append(group)
        lines.append(f"  {check.status} {check.text}")
    failures = sum(check.status == FAIL for check in checks)
    lines.append("")
    if failures:
        lines.append(
            f"{failures} problema{'s' if failures != 1 else ''}: corrige lo marcado con {FAIL} "
            "y vuelve a ejecutar `modelduel doctor`."
        )
    elif config_found:
        lines.append("Todo listo: lanza el duelo con `modelduel run`.")
    else:
        lines.append(
            "Todo listo. Sin claves: `modelduel demo`. "
            "Para tu propio duelo: `modelduel init` y después `modelduel run`."
        )
    return "\n".join(lines), 1 if failures else 0
