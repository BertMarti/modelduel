"""Tareas en JavaScript y TypeScript (experimental, 1.1.0): formato, Node y el runner endurecido.

Las pruebas que ejecutan Node de verdad se saltan si no hay un Node >= 20.11 en el PATH (las de
TypeScript, si no es >= 22.6). Ninguna usa Docker real: el contenedor se prueba con la orden y
con un «docker» falso (el de verdad, solo en el CI con ``MODELDUEL_TEST_DOCKER=1``).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import textwrap
import time
from pathlib import Path

import pytest

from modelduel import node, runner
from modelduel.duel import run_duel
from modelduel.extract import extract_code
from modelduel.node import (
    MIN_NODE,
    MIN_NODE_TS,
    NodeError,
    NodeInfo,
    check_node,
    needs_strip_flag,
    node_test_args,
    parse_version,
    permission_flag,
    probe_node,
)
from modelduel.providers.replay import ReplayProvider
from modelduel.runner import RunnerError, build_prompt, ensure_runtimes, run_tests
from modelduel.sandbox import NODE_IMAGE, Sandbox, container_command, node_image_version
from modelduel.tasks import TaskError, count_node_tests, discover_tasks, load_task

ROOT = Path(__file__).resolve().parent.parent
JS_EXAMPLES = ROOT / "examples" / "tasks-js"
NODE = node.find_node()
HAS_NODE = NODE is not None and NODE.version >= MIN_NODE
HAS_NODE_TS = NODE is not None and NODE.version >= MIN_NODE_TS
needs_node = pytest.mark.skipif(not HAS_NODE, reason="hace falta Node >= 20.11 en el PATH")
needs_node_ts = pytest.mark.skipif(not HAS_NODE_TS, reason="TypeScript necesita Node >= 22.6")
linux = pytest.mark.skipif(
    not runner.supervisor_supported(), reason="supervisor y /proc solo en Linux"
)

ADD_JS_TESTS = """\
import { test } from "node:test";
import assert from "node:assert/strict";
import { add } from "./solution.mjs";

test("positivos", () => {
  assert.equal(add(2, 3), 5);
});

test("negativos", () => {
  assert.equal(add(-2, -3), -5);
});

test("cero", () => {
  assert.equal(add(0, 0), 0);
});
"""
GOOD_JS = "export function add(a, b) {\n  return a + b;\n}\n"


@pytest.fixture
def make_js_task(tmp_path: Path):
    """Tarea mínima de JavaScript (o TypeScript) en ``tmp_path``."""

    def _make(
        tests: str = ADD_JS_TESTS,
        name: str = "suma_js",
        language: str | None = "javascript",
        test_file: str = "test_task.mjs",
    ):
        folder = tmp_path / "tasks" / name
        folder.mkdir(parents=True)
        (folder / "task.md").write_text("# Suma\n\nEscribe `add(a, b)`.", encoding="utf-8")
        (folder / test_file).write_text(tests, encoding="utf-8")
        if language is not None:
            (folder / "meta.toml").write_text(f'language = "{language}"\n', encoding="utf-8")
        return load_task(folder)

    return _make


# ---------------------------------------------------------------- formato de tarea


def test_las_tareas_de_ejemplo_declaran_su_lenguaje():
    tasks = discover_tasks(JS_EXAMPLES)
    by_id = {task.id: task for task in tasks}
    assert by_id["format_bytes"].language == "javascript"
    assert by_id["format_bytes"].test_path.name == "test_task.mjs"
    assert by_id["group_by"].language == "typescript"
    assert by_id["group_by"].test_path.name == "test_task.ts"
    for task in tasks:
        assert task.expected_tests >= 6


def test_las_tareas_de_python_siguen_igual(examples_dir):
    tasks = discover_tasks(examples_dir / "tasks")
    assert {task.language for task in tasks} == {"python"}


def test_el_lenguaje_se_deduce_del_archivo_de_tests(make_js_task):
    task = make_js_task(language=None)
    assert task.language == "javascript"


def test_alias_js_y_ts(make_js_task):
    assert make_js_task(language="js").language == "javascript"


def test_lenguaje_desconocido_da_error_claro(make_js_task):
    with pytest.raises(TaskError, match="«language» debe ser uno de"):
        make_js_task(language="rust")


def test_lenguaje_declarado_sin_su_archivo_de_tests(make_js_task):
    with pytest.raises(TaskError, match="no tiene test_task.ts"):
        make_js_task(language="typescript")


def test_dos_archivos_de_tests_sin_declarar_lenguaje(tmp_path):
    folder = tmp_path / "doble"
    folder.mkdir()
    (folder / "task.md").write_text("# Doble", encoding="utf-8")
    (folder / "test_task.py").write_text("def test_a():\n    pass\n", encoding="utf-8")
    (folder / "test_task.mjs").write_text('test("a", () => {});\n', encoding="utf-8")
    with pytest.raises(TaskError, match="declara cuál vale"):
        load_task(folder)
    (folder / "meta.toml").write_text('language = "javascript"\n', encoding="utf-8")
    assert load_task(folder).language == "javascript"


def test_tests_de_node_sin_ninguna_llamada_test(make_js_task):
    with pytest.raises(TaskError, match="ninguna llamada test"):
        make_js_task(tests='import { test } from "node:test";\n// test("a")\n')


def test_contar_tests_de_node():
    source = textwrap.dedent(
        """\
        // test("comentado")
        /* test("también comentado") */
        test("uno", () => {});
          test.skip("dos", () => {});
        test.todo("tres");
        it("cuatro", () => {});
        test("con subtests", async (t) => {
          await t.test("no cuenta", () => {});
        });
        """
    )
    assert count_node_tests(source) == 5


def test_el_prompt_pide_un_modulo_es_del_lenguaje(make_js_task):
    js = build_prompt(make_js_task())
    assert "```javascript" in js and "export function" in js and "```python" not in js
    ts = build_prompt(make_js_task(name="ts", language="typescript", test_file="test_task.ts"))
    assert "```typescript" in ts and "enum" in ts


def test_extraer_el_bloque_del_lenguaje_de_la_tarea():
    text = "```python\nprint(1)\n```\n\n```js\nexport function f() {}\n```\n"
    assert extract_code(text, "javascript") == "export function f() {}\n"
    assert extract_code(text) == "print(1)\n"
    ts = "```typescript\nexport function g(x: number) {}\n```\n```js\nexport function h() {}\n```"
    assert extract_code(ts, "typescript").startswith("export function g")
    only_js = "```javascript\nexport function h() {}\n```"
    assert extract_code(only_js, "typescript") == "export function h() {}\n"


# ---------------------------------------------------------------- versión y opciones de Node


def test_versiones_de_node():
    assert parse_version("v22.6.0\n") == (22, 6, 0)
    assert parse_version("basura") is None
    assert needs_strip_flag((22, 6, 0)) and needs_strip_flag((23, 5, 9))
    assert not needs_strip_flag((22, 18, 0)) and not needs_strip_flag((24, 0, 0))
    assert permission_flag((20, 19, 2)) == "--experimental-permission"
    assert permission_flag((22, 12, 0)) == "--experimental-permission"
    assert permission_flag((22, 13, 0)) == "--permission"
    assert permission_flag((23, 4, 0)) == "--experimental-permission"
    assert permission_flag((24, 1, 0)) == "--permission"


def test_probe_node_sin_node_o_con_salida_rara():
    assert probe_node(which=lambda _n: None) is None

    class Done:
        returncode = 0
        stdout = "v20.19.2\n"

    info = probe_node(which=lambda _n: "/usr/bin/node", run=lambda *_a, **_k: Done())
    assert info == NodeInfo("/usr/bin/node", (20, 19, 2)) and info.text == "v20.19.2"
    Done.stdout = "no soy node"
    assert probe_node(which=lambda _n: "/x/node", run=lambda *_a, **_k: Done()) is None


def test_sin_node_el_error_dice_que_instalar():
    with pytest.raises(NodeError, match="no encuentro `node` en el PATH") as exc:
        check_node({"javascript"}, None)
    assert "nodejs.org" in str(exc.value) and "20.11.0" in str(exc.value)
    assert check_node({"python"}, None) is None  # Python no necesita Node


def test_typescript_con_node_viejo_pide_actualizar():
    old = NodeInfo("/usr/bin/node", (20, 19, 2))
    assert check_node({"javascript"}, old) is old
    with pytest.raises(NodeError, match=r"22\.6\.0 o más nuevo \(tienes v20\.19\.2"):
        check_node({"typescript", "javascript"}, old)


def test_opciones_de_node_con_permisos_limitados_a_la_ejecucion():
    args = node_test_args(
        (22, 6, 0), "typescript", root="/r", reporter="file:///r/rep.mjs", test_file="test_task.ts"
    )
    assert args[:3] == ["--experimental-permission", "--allow-fs-read=/r", "--allow-fs-write=/r"]
    assert "--test-reporter=file:///r/rep.mjs" in args
    assert "--disable-wasm-trap-handler" in args  # WebAssembly dentro del límite de memoria
    old_node = node_test_args((20, 11, 0), "javascript", root="/r", reporter="r", test_file="t")
    assert "--disable-wasm-trap-handler" not in old_node  # la opción no existía aún
    assert "--experimental-strip-types" in args
    assert args[-1] == "test_task.ts"
    # Nada de procesos hijos, workers ni complementos: esas opciones nunca se añaden.
    assert not any(
        a.startswith(("--allow-child", "--allow-worker", "--allow-addons")) for a in args
    )
    modern = node_test_args((24, 1, 0), "typescript", root="/r", reporter="r", test_file="t.ts")
    assert modern[0] == "--permission" and "--experimental-strip-types" not in modern


def test_recuento_del_reporter(tmp_path):
    path = tmp_path / "r.json"
    assert node.parse_node_results(path) is None
    path.write_text('{"passed": 2, "failed": 1, "skipped": 1}', encoding="utf-8")
    counts = node.parse_node_results(path)
    assert counts["total"] == 4 and counts["errors"] == 0 and not counts["collection_error"]
    for bad in ('{"passed": -1, "failed": 0, "skipped": 0}', '{"passed": true}', "[]", "{"):
        path.write_text(bad, encoding="utf-8")
        assert node.parse_node_results(path) is None
    assert '"C:\\\\x\\\\r.json"' in node.reporter_source("C:\\x\\r.json")


@needs_node
def test_el_reporter_cuenta_solo_los_tests_hoja(make_js_task):
    tests = textwrap.dedent(
        """\
        import { test, describe, it } from "node:test";
        import assert from "node:assert/strict";
        import { add } from "./solution.mjs";
        test("a", () => assert.equal(add(1, 1), 2));
        test("b", () => assert.equal(add(1, 1), 3));
        test.skip("c", () => {});
        test("padre", async (t) => {
          await t.test("h1", () => {});
          await t.test("h2", () => {});
        });
        describe("suite", () => {
          it("i1", () => {});
        });
        """
    )
    result = run_tests(GOOD_JS, make_js_task(tests), timeout=30)
    # a, h1, h2, i1 pasan; b falla; c se salta (el padre y la suite no cuentan).
    assert (result.passed, result.failed, result.skipped) == (4, 1, 1), result.output


def test_sin_node_el_duelo_para_antes_de_empezar(make_js_task, monkeypatch):
    monkeypatch.setattr(runner, "find_node", lambda: None)
    with pytest.raises(RunnerError, match="no encuentro `node`"):
        ensure_runtimes([make_js_task()], Sandbox())
    # En un contenedor Node viene en la imagen: no hace falta en local.
    ensure_runtimes([make_js_task(name="otra")], Sandbox(kind="docker", executable="/x"))


def test_sin_node_run_tests_no_ejecuta_nada(make_js_task, monkeypatch):
    monkeypatch.setattr(runner, "find_node", lambda: None)
    with pytest.raises(RunnerError, match="Node.js"):
        run_tests(GOOD_JS, make_js_task(), timeout=5, sandbox=Sandbox())


def test_entorno_de_node_sin_opciones_del_anfitrion():
    env = node.node_env({"NODE_OPTIONS": "--require /x.js", "NODE_PATH": "/y", "A": "b"})
    assert "NODE_OPTIONS" not in env and "NODE_PATH" not in env
    assert env["A"] == "b" and env["NO_COLOR"] == "1"


# ---------------------------------------------------------------- contenedor (sin Docker real)


def test_orden_del_contenedor_para_node(tmp_path):
    box = Sandbox(kind="docker", executable="/usr/bin/docker", user_args=("--user", "1000:1000"))
    args = node_test_args(
        node_image_version(),
        "javascript",
        root="/sandbox",
        reporter="file:///sandbox/modelduel-reporter.mjs",
        test_file="test_task.mjs",
    )
    cmd = container_command(
        box, name="modelduel-x", root=tmp_path, python_args=args, timeout=7, program="node"
    )
    text = " ".join(cmd)
    for part in ("--network none", "--cap-drop ALL", "--read-only", "--pids-limit 128"):
        assert part in text
    after = cmd[cmd.index(NODE_IMAGE) + 1 :]
    assert after[:5] == ["-s", "KILL", "7", "sh", "-c"]
    assert after[5].endswith('exec node "$@"') and after[7:] == args
    assert "/deps" not in text and "PYTHONPATH" not in text  # sin pytest montado
    assert "--allow-fs-write=/sandbox" in cmd
    assert NODE_IMAGE.startswith("node:22.") and "@sha256:" in NODE_IMAGE
    assert node_image_version() >= (22, 18, 0)  # borra tipos sin opciones


def test_en_el_contenedor_node_arranca_con_los_mismos_limites():
    from modelduel.sandbox import node_ulimit_script

    script = node_ulimit_script(runner.resource_limits(20))
    assert script == (
        "ulimit -v 4194304 && ulimit -f 524288 && ulimit -n 256 && ulimit -c 0 && "
        'ulimit -S -t 25 && ulimit -H -t 26 && exec node "$@"'
    )


def test_preparar_el_contenedor_solo_descarga_las_imagenes_necesarias():
    from modelduel.sandbox import DEFAULT_IMAGE, images_for

    box = Sandbox(kind="docker", executable="/x")
    assert images_for(box, {"javascript"}) == [NODE_IMAGE]
    assert images_for(box, {"python", "typescript"}) == [DEFAULT_IMAGE, NODE_IMAGE]
    assert images_for(box, ("python",)) == [DEFAULT_IMAGE]


# ---------------------------------------------------------------- ejecución real con Node


@needs_node
def test_solucion_correcta_resuelve(make_js_task):
    result = run_tests(GOOD_JS, make_js_task(), timeout=30)
    assert result.solved, result.output
    assert (result.passed, result.total) == (3, 3)
    assert "<tmp>" in result.output or "positivos" in result.output


@needs_node
def test_solucion_que_falla_un_test(make_js_task):
    code = "export function add(a, b) {\n  return a + b + (a < 0 ? 1 : 0);\n}\n"
    result = run_tests(code, make_js_task(), timeout=30)
    assert result.status == "ok" and not result.solved
    assert (result.passed, result.failed, result.total) == (2, 1, 3)
    assert "negativos" in result.output


@needs_node
@pytest.mark.parametrize(
    "code",
    [
        "export function add(a, b) { return a + ; }\n",  # error de sintaxis
        "export function sumar(a, b) { return a + b; }\n",  # falta el export pedido
        "module.exports = { add: (a, b) => a + b };\n",  # CommonJS en un módulo ES
    ],
)
def test_solucion_que_no_carga_es_error_de_importacion(make_js_task, code):
    result = run_tests(code, make_js_task(), timeout=30)
    assert result.status == "import_error" and not result.solved
    assert result.total == 3


@needs_node
def test_sin_bloque_de_codigo(make_js_task):
    result = run_tests(None, make_js_task(), timeout=30)
    assert result.status == "no_code" and result.total == 3


# ---------------------------------------------------------------- soluciones maliciosas


@needs_node
def test_bucle_infinito_agota_el_tiempo(make_js_task):
    code = "export function add(a, b) {\n  for (;;) {}\n}\n"
    start = time.monotonic()
    result = run_tests(code, make_js_task(), timeout=2)
    assert result.status == "timeout" and not result.solved
    assert time.monotonic() - start < 2 + runner.SUPERVISOR_GRACE_S + 5


@needs_node
def test_bucle_infinito_al_cargar_tambien(make_js_task):
    code = "while (true) {}\nexport function add(a, b) { return a + b; }\n"
    result = run_tests(code, make_js_task(), timeout=2)
    assert result.status == "timeout"


def _procs_with(token: str) -> list[int]:
    found = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/cmdline", "rb") as fh:
                if token.encode() in fh.read():
                    found.append(int(name))
        except OSError:
            continue
    return found


@needs_node
@linux
def test_fork_bomb_acotada_no_lanza_ningun_proceso(make_js_task):
    """Intenta lanzar 20 procesos que se desligan (``detached``) y un *worker* por cada uno."""
    token = f"modelduel-bomba-{os.getpid()}"
    code = textwrap.dedent(
        f"""\
        import {{ spawn, execFileSync, fork }} from "node:child_process";
        import {{ Worker }} from "node:worker_threads";
        let hijos = 0, bloqueados = 0;
        for (let i = 0; i < 20; i++) {{
          for (const lanzar of [
            () => spawn("sleep", ["300", "{token}"], {{ detached: true, stdio: "ignore" }}),
            () => execFileSync("sleep", ["300", "{token}"]),
            () => fork("solution.mjs", ["{token}"], {{ detached: true }}),
            () => new Worker("while (true) {{}}", {{ eval: true }}),
          ]) {{
            try {{ lanzar(); hijos++; }} catch (e) {{ bloqueados++; }}
          }}
        }}
        console.log(`hijos=${{hijos}} bloqueados=${{bloqueados}}`);
        export function add(a, b) {{ return a + b; }}
        """
    )
    result = run_tests(code, make_js_task(), timeout=20)
    assert "hijos=0 bloqueados=80" in result.output, result.output
    assert result.solved  # bloquearlo no rompe una solución que, por lo demás, es correcta
    assert _procs_with(token) == []


@needs_node
def test_escribir_o_leer_fuera_de_la_carpeta_se_bloquea(make_js_task, tmp_path, monkeypatch):
    outside = tmp_path / "fuera"
    outside.mkdir()
    secret = outside / "secreto.txt"
    secret.write_text("no deberías leerme", encoding="utf-8")
    target = outside / "escrito-por-la-solucion.txt"
    monkeypatch.setenv("MODELDUEL_PRUEBA_FUERA", str(outside))
    code = textwrap.dedent(
        """\
        import fs from "node:fs";
        import path from "node:path";
        const fuera = process.env.MODELDUEL_PRUEBA_FUERA;
        const intentos = {
          escribir: () => fs.writeFileSync(path.join(fuera, "escrito-por-la-solucion.txt"), "x"),
          leer: () => fs.readFileSync(path.join(fuera, "secreto.txt"), "utf8"),
          home: () => fs.writeFileSync(path.join(fuera, "..", "home.txt"), "x"),
          symlink: () => fs.symlinkSync(path.join(fuera, "secreto.txt"), "enlace.txt"),
        };
        for (const [nombre, intento] of Object.entries(intentos)) {
          try { intento(); console.log(`${nombre}=PERMITIDO`); }
          catch (e) { console.log(`${nombre}=${e.code}`); }
        }
        export function add(a, b) { return a + b; }
        """
    )
    result = run_tests(code, make_js_task(), timeout=20)
    assert "PERMITIDO" not in result.output, result.output
    assert "escribir=ERR_ACCESS_DENIED" in result.output
    assert "leer=ERR_ACCESS_DENIED" in result.output
    assert not target.exists() and not (tmp_path / "home.txt").exists()
    assert "no deberías leerme" not in result.output


@needs_node
def test_los_secretos_del_entorno_no_llegan_a_node(make_js_task, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "sk-no-debe-llegar")
    monkeypatch.setenv("NODE_OPTIONS", "--title=inyectado")
    code = textwrap.dedent(
        """\
        console.log("clave=" + (process.env.OPENAI_API_KEY ?? "ninguna"));
        console.log("opciones=" + (process.env.NODE_OPTIONS ?? "ninguna"));
        console.log("home=" + (process.env.HOME === process.env.TMPDIR));
        export function add(a, b) { return a + b; }
        """
    )
    result = run_tests(code, make_js_task(), timeout=20)
    assert "sk-no-debe-llegar" not in result.output
    assert "clave=ninguna" in result.output and "opciones=ninguna" in result.output
    assert "home=true" in result.output
    assert result.solved


@needs_node
@pytest.mark.skipif(
    not runner.network_isolation_available() or not runner.supervisor_supported(),
    reason="la red solo se corta en Linux con espacios de nombres",
)
def test_sin_red_por_defecto_en_linux(make_js_task):
    code = textwrap.dedent(
        """\
        import net from "node:net";
        export function add(a, b) { return a + b; }
        export const red = await new Promise((resolve) => {
          const s = net.connect({ host: "192.0.2.1", port: 9, timeout: 2000 });
          s.on("connect", () => resolve("CONECTADA"));
          s.on("error", (e) => resolve(e.code));
          s.on("timeout", () => resolve("timeout"));
        });
        console.log("red=" + red);
        """
    )
    result = run_tests(code, make_js_task(), timeout=20)
    assert "red=CONECTADA" not in result.output
    assert "red=ENETUNREACH" in result.output, result.output


@needs_node
def test_terminar_el_proceso_a_mitad_no_cuenta_como_resuelta(make_js_task):
    code = textwrap.dedent(
        """\
        let llamadas = 0;
        export function add(a, b) {
          if (++llamadas === 2) process.exit(0);
          return a + b;
        }
        """
    )
    result = run_tests(code, make_js_task(), timeout=20)
    assert not result.solved
    assert result.status in ("error", "ok")
    if result.status == "ok":
        assert result.passed < result.total == 3


@needs_node
def test_al_cargar_process_exit_cero_no_es_resuelta(make_js_task):
    code = "process.exit(0);\nexport function add(a, b) { return a + b; }\n"
    result = run_tests(code, make_js_task(), timeout=20)
    assert result.status == "error" and not result.solved


@needs_node
@pytest.mark.skipif(os.name == "nt", reason="setrlimit solo en POSIX")
def test_limite_de_tamano_de_archivo(make_js_task, monkeypatch):
    monkeypatch.setattr(runner, "FILE_SIZE_LIMIT_BYTES", 1024 * 1024)
    code = textwrap.dedent(
        """\
        import fs from "node:fs";
        fs.writeFileSync("grande.bin", Buffer.alloc(4 * 1024 * 1024));
        export function add(a, b) { return a + b; }
        """
    )
    result = run_tests(code, make_js_task(), timeout=20)
    assert not result.solved
    assert result.message == runner.file_size_message(), result.message


@needs_node
def test_agotar_la_memoria_de_node(make_js_task, monkeypatch):
    monkeypatch.setattr(node, "NODE_HEAP_MB", 32)
    code = textwrap.dedent(
        """\
        const montón = [];
        export function add(a, b) {
          for (;;) montón.push(new Array(1e5).fill(Math.random()));
        }
        """
    )
    result = run_tests(code, make_js_task(), timeout=30)
    assert not result.solved
    assert result.status != "ok"
    assert "memoria de Node" in result.message, (result.message, result.output[-500:])


# ---------------------------------------------------------------- TypeScript


TS_TESTS = """\
import { test } from "node:test";
import assert from "node:assert/strict";
import { add } from "./solution.ts";

test("suma", () => {
  const n: number = add(2, 3);
  assert.equal(n, 5);
});
"""


@needs_node_ts
def test_typescript_borra_los_tipos_y_resuelve(make_js_task):
    task = make_js_task(TS_TESTS, name="ts", language="typescript", test_file="test_task.ts")
    code = "export function add(a: number, b: number): number {\n  return a + b;\n}\n"
    result = run_tests(code, task, timeout=30)
    assert result.solved, result.output


@needs_node_ts
def test_typescript_con_enum_no_carga(make_js_task):
    task = make_js_task(TS_TESTS, name="ts", language="typescript", test_file="test_task.ts")
    code = "enum E { A }\nexport function add(a: number, b: number): number { return a + b; }\n"
    result = run_tests(code, task, timeout=30)
    assert result.status == "import_error"


# ---------------------------------------------------------------- de principio a fin


@needs_node
def test_duelo_con_las_tareas_js_de_ejemplo(examples_dir):
    tasks = [t for t in discover_tasks(JS_EXAMPLES) if t.language == "javascript"]
    providers = {
        side: ReplayProvider(name, [examples_dir / "replays"])
        for side, name in (("a", "alfa"), ("b", "beta"), ("c", "gamma"))
    }
    results = run_duel(tasks, providers, {}, timeout=30)
    entry = results["tasks"][0]
    assert entry["language"] == "javascript"
    solved = {side: entry["results"][side][0]["solved"] for side in "abc"}
    assert solved == {"a": True, "b": False, "c": True}


@needs_node_ts
def test_duelo_con_la_tarea_ts_de_ejemplo(examples_dir):
    tasks = [t for t in discover_tasks(JS_EXAMPLES) if t.language == "typescript"]
    providers = {
        side: ReplayProvider(name, [examples_dir / "replays"])
        for side, name in (("a", "alfa"), ("b", "beta"), ("c", "gamma"))
    }
    results = run_duel(tasks, providers, {}, timeout=30)
    entry = results["tasks"][0]
    solved = {side: entry["results"][side][0]["solved"] for side in "abc"}
    assert solved == {"a": True, "b": True, "c": False}


# ---------------------------------------------------------------- docker falso para Node

FAKE_NODE_DOCKER = r'''
"""docker falso: ejecuta en local con node lo que iría en el contenedor (solo para tests)."""
import os, shutil, subprocess, sys
args = [os.path.basename(sys.argv[0]), *sys.argv[1:]]
if args[0] != "run":
    sys.exit(0)
root = None
for i, part in enumerate(args):
    if part == "--mount" and args[i + 1].endswith("target=/sandbox"):
        root = args[i + 1].split("source=")[1].split(",target=")[0]
image_at = args.index(os.environ["FAKE_DOCKER_IMAGE"])
_, _, seconds, program, *rest = args[image_at + 1:]
assert program == "sh" and rest[0] == "-c", (program, rest[:1])
root = os.path.realpath(root)
rest = [part.replace("/sandbox", root) for part in rest]
# Dentro del contenedor el reporter escribe en /sandbox; aquí, en la carpeta real.
reporter = os.path.join(root, "modelduel-reporter.mjs")
with open(reporter, encoding="utf-8") as fh:
    source = fh.read()
with open(reporter, "w", encoding="utf-8") as fh:
    fh.write(source.replace('"/sandbox/', '"' + root + "/"))
try:
    # El sh real aplica los ulimit y hace exec del node del anfitrión (como en la imagen).
    proc = subprocess.run(["sh", *rest], cwd=os.path.join(root, "work"),
                          timeout=float(seconds))
except subprocess.TimeoutExpired:
    sys.exit(124)
sys.exit(proc.returncode)
'''


@needs_node
@pytest.mark.skipif(os.name == "nt", reason="el docker falso usa sh, como la imagen de Node")
def test_contenedor_falso_para_node(make_js_task, tmp_path, monkeypatch):
    folder = tmp_path / "docker-falso"
    folder.mkdir()
    for verb in ("run", "rm"):
        (folder / verb).write_text(FAKE_NODE_DOCKER, encoding="utf-8")
    monkeypatch.chdir(folder)
    monkeypatch.setenv("FAKE_DOCKER_IMAGE", NODE_IMAGE)
    monkeypatch.setattr(
        "modelduel.runner.node_image_version", lambda _image=None: NODE.version if NODE else None
    )
    box = Sandbox(kind="docker", executable=sys.executable)
    task = make_js_task()
    result = run_tests(GOOD_JS, task, timeout=30, sandbox=box)
    assert result.solved, result.output
    assert "/sandbox" not in result.output
    # Los ulimit del contenedor se aplican de verdad: un archivo mayor que el límite falla.
    monkeypatch.setattr(runner, "FILE_SIZE_LIMIT_BYTES", 1024 * 1024)
    big = (
        'import fs from "node:fs";\n'
        'fs.writeFileSync("grande.bin", Buffer.alloc(4 * 1024 * 1024));\n' + GOOD_JS
    )
    result = run_tests(big, make_js_task(name="grande"), timeout=30, sandbox=box)
    assert not result.solved and result.message == runner.file_size_message(), result.output


@needs_node
def test_codigo_de_salida_cambiado_no_cuenta_como_resuelta(make_js_task):
    code = "process.exitCode = 3;\n" + GOOD_JS
    result = run_tests(code, make_js_task(), timeout=20)
    assert result.passed == 3 and not result.solved
    assert result.status == "error" and "código 3" in result.message


# ---------------------------------------------------------------- Docker de verdad (solo CI)

real_docker = pytest.mark.skipif(
    os.environ.get("MODELDUEL_TEST_DOCKER") != "1" or shutil.which("docker") is None,
    reason="Docker real solo con MODELDUEL_TEST_DOCKER=1 (lo activa el CI de Ubuntu)",
)

HOSTILE_JS_TESTS = """\
import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import net from "node:net";
import { add } from "./solution.mjs";

test("suma", () => {
  assert.equal(add(2, 3), 5);
});

test("sin red", async () => {
  const r = await new Promise((resolve) => {
    const s = net.connect({ host: "192.0.2.1", port: 9, timeout: 2000 });
    s.on("connect", () => resolve("CONECTADA"));
    s.on("error", (e) => resolve(e.code));
    s.on("timeout", () => resolve("timeout"));
  });
  assert.notEqual(r, "CONECTADA");
});

test("sin escribir fuera", () => {
  assert.throws(() => fs.writeFileSync("/tmp/fuera.txt", "x"));
});

test("sin root y sin secretos", () => {
  assert.notEqual(process.getuid(), 0);
  assert.equal(process.env.OPENAI_API_KEY, undefined);
  assert.equal(process.env.HOME, "/tmp");
});
"""


@real_docker
def test_docker_de_verdad_con_node(make_js_task, monkeypatch):
    from modelduel.sandbox import prepare_container, resolve_sandbox

    monkeypatch.setenv("OPENAI_API_KEY", "sk-no-debe-llegar")
    box = prepare_container(resolve_sandbox("docker"), languages={"javascript"})
    result = run_tests(GOOD_JS, make_js_task(HOSTILE_JS_TESTS), timeout=60, sandbox=box)
    assert result.solved, result.output


@real_docker
def test_docker_de_verdad_con_typescript(examples_dir):
    from modelduel.sandbox import prepare_container, resolve_sandbox

    box = prepare_container(resolve_sandbox("docker"), languages={"typescript"})
    task = next(t for t in discover_tasks(JS_EXAMPLES) if t.language == "typescript")
    code = extract_code(
        (examples_dir / "replays" / "alfa" / f"{task.id}.md").read_text(encoding="utf-8"),
        "typescript",
    )
    result = run_tests(code, task, timeout=60, sandbox=box)
    assert result.solved, result.output


# ---------------------------------------------------------------- init, doctor e informe


def test_init_js_y_ts_anaden_sus_tareas(tmp_path, monkeypatch, capsys):
    from modelduel.cli import main

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--js", "--ts"]) == 0
    out = capsys.readouterr().out
    tasks = {t.id: t.language for t in discover_tasks(tmp_path / "mi-duelo" / "tasks")}
    assert tasks["format_bytes"] == "javascript" and tasks["group_by"] == "typescript"
    assert "incluye una en JavaScript" in out and "Node 22.6" in out
    replays = tmp_path / "mi-duelo" / "replays"
    assert (replays / "alfa" / "format_bytes.md").is_file()


def test_init_sin_opciones_no_anade_tareas_de_node(tmp_path, monkeypatch, capsys):
    from modelduel.cli import main

    monkeypatch.chdir(tmp_path)
    assert main(["init"]) == 0
    tasks = discover_tasks(tmp_path / "mi-duelo" / "tasks")
    assert {t.language for t in tasks} == {"python"}


@needs_node
def test_primer_duelo_tras_init_js(tmp_path, monkeypatch, capsys):
    from modelduel.cli import main

    monkeypatch.chdir(tmp_path)
    assert main(["init", "--js"]) == 0
    monkeypatch.chdir(tmp_path / "mi-duelo")
    assert main(["run", "tasks/format_bytes", "--out", "js"]) == 0
    out = capsys.readouterr().out
    assert "Tareas con Node (experimental): 1 en JavaScript" in out
    html = (tmp_path / "mi-duelo" / "js" / "index.html").read_text(encoding="utf-8")
    assert "fácil · JavaScript" in html and "Salida de node:test" in html
    assert 'class="language-javascript"' in html


def test_run_sin_node_para_antes_de_llamar_a_ninguna_api(tmp_path, monkeypatch, capsys):
    from modelduel.cli import EXIT_USAGE, main

    monkeypatch.setattr(runner, "find_node", lambda: None)
    called = []
    monkeypatch.setattr(
        "modelduel.duel.run_attempt", lambda *a, **k: called.append(1) or pytest.fail("API")
    )
    code = main(
        [
            "run",
            str(JS_EXAMPLES / "format_bytes"),
            "--model",
            "replay:alfa",
            "--model",
            "replay:beta",
            "--out",
            str(tmp_path / "o"),
        ]
    )
    err = capsys.readouterr().err
    assert code == EXIT_USAGE and not called
    assert "no encuentro `node` en el PATH" in err


def test_doctor_informa_de_node():
    from modelduel.doctor import FAIL, INFO, OK, WARN, node_check

    assert node_check(None).status == INFO and "solo hace falta" in node_check(None).text
    assert node_check(NodeInfo("/n", (18, 20, 0))).status == WARN
    js_only = node_check(NodeInfo("/n", (20, 19, 2)))
    assert js_only.status == OK and "TypeScript necesita 22.6" in js_only.text
    both = node_check(NodeInfo("/n", (22, 23, 4)))
    assert both.status == OK and "JavaScript y TypeScript" in both.text
    assert FAIL != OK


def test_doctor_falla_si_la_config_tiene_tareas_ts_y_node_es_viejo(tmp_path):
    from modelduel.doctor import FAIL, config_checks

    tasks = tmp_path / "tasks"
    shutil.copytree(JS_EXAMPLES, tasks)
    config = tmp_path / "modelduel.toml"
    config.write_text('tareas = "tasks"\nmodelos = ["replay:alfa", "replay:beta"]\n')
    checks, _ = config_checks(config, {}, node_info=lambda: NodeInfo("/n", (20, 19, 2)))
    assert any("2 en JavaScript/TypeScript" in c.text for c in checks)
    assert any(c.status == FAIL and "22.6.0 o más nuevo" in c.text for c in checks)
    # Con contenedor, Node viene en la imagen.
    config.write_text(config.read_text() + 'aislamiento = "docker"\n')
    checks, _ = config_checks(config, {}, node_info=lambda: None)
    assert not any(c.status == FAIL for c in checks)


def test_informes_muestran_el_lenguaje():
    from modelduel.report.html import task_meta
    from modelduel.report.markdown import render_markdown

    assert task_meta({"difficulty": "fácil", "language": "javascript"}) == (
        "<span>fácil · JavaScript</span>"
    )
    # Un results.json anterior a la 1.1.0 no tiene «language»: es Python.
    assert task_meta({}) == "<span>Python</span>"
    results = json.loads((ROOT / "results").glob("*.json").__next__().read_text("utf-8"))
    results["tasks"][0]["language"] = "typescript"
    assert "(TypeScript)" in render_markdown(results)
