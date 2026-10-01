// Lógica pura de site/demo.js. Sin dependencias: node --test tests/js
const test = require("node:test");
const assert = require("node:assert/strict");
const core = require("../../site/demo.js");

const attempt = (over) => ({
  status: "ok", passed: 8, total: 8, latency_s: 2, input_tokens: 400, output_tokens: 200,
  output: "........  [100%]\n", code: "x = 1\n", ...over,
});
const task = (a, b, c) => ({
  id: "slugify", title: "Slugify", statement: "# Enunciado\n\nHaz algo.", tests_expected: 8,
  results: { a: [a], b: [b], c: [c] },
});
const contenders = { a: { spec: "replay:alfa" }, b: { spec: "replay:beta" }, c: { spec: "replay:gamma" } };

test("la duración total son ~25 s y hay cuatro fases", () => {
  assert.equal(core.DURATION, 25);
  assert.equal(core.PHASES.length, 4);
});

test("phaseAt reparte el tiempo en fases y se queda en la última", () => {
  assert.equal(core.phaseAt(0), 0);
  assert.equal(core.phaseAt(3), 0);
  assert.equal(core.phaseAt(3.1), 1);
  assert.equal(core.phaseAt(12.1), 2);
  assert.equal(core.phaseAt(20.1), 3);
  assert.equal(core.phaseAt(99), 3);
});

test("el código se escribe a ritmo proporcional a la latencia", () => {
  const code = "x".repeat(1000);
  // El más lento tarda WRITE_S; uno con la mitad de latencia, la mitad.
  const slow = core.typedLength(code, 3 + core.WRITE_S / 2, 8, 8);
  const fast = core.typedLength(code, 3 + core.WRITE_S / 2, 4, 8);
  assert.equal(slow, 500);
  assert.equal(fast, 1000);
  assert.equal(core.typedLength(code, 0, 8, 8), 0);
  assert.equal(core.typedLength(code, 99, 8, 8), 1000);
});

test("typedLength no revienta con latencias raras", () => {
  for (const lat of [0, null, undefined, -3, NaN]) {
    assert.equal(core.typedLength("abc", 99, lat, lat), 3);
  }
});

test("testMarks lee la línea de progreso de pytest", () => {
  const marks = core.testMarks(attempt({ passed: 6, output: "....FF..   [100%]\n" }), 8);
  assert.deepEqual(marks, ["pass", "pass", "pass", "pass", "fail", "fail", "pass", "pass"]);
});

test("testMarks suma varias líneas y distingue omitidos", () => {
  const marks = core.testMarks(attempt({ total: 6, passed: 4, output: "..s..F  [ 50%]\n  [100%]\n" }), 6);
  assert.deepEqual(marks, ["pass", "pass", "skip", "pass", "pass", "fail"]);
});

test("testMarks recurre a passed/total si la salida no cuadra", () => {
  const marks = core.testMarks(attempt({ passed: 2, total: 4, output: "ruido" }), 4);
  assert.deepEqual(marks, ["pass", "pass", "fail", "fail"]);
});

test("testMarks acota el número de tests", () => {
  const marks = core.testMarks(attempt({ passed: 5000, total: 5000, output: "" }), 5000);
  assert.equal(marks.length, core.MAX_TESTS);
});

test("testsDone avanza uno a uno durante la fase de tests", () => {
  assert.equal(core.testsDone(8, 12), 0);
  assert.equal(core.testsDone(8, 20), 8);
  assert.equal(core.testsDone(8, 99), 8);
  const mid = core.testsDone(8, 16);
  assert.ok(mid > 0 && mid < 8);
  assert.equal(core.testsDone(0, 16), 0);
});

test("tokensAt sube con el avance y acaba en el total", () => {
  assert.equal(core.tokensAt(200, 0), 0);
  assert.equal(core.tokensAt(200, 0.5), 100);
  assert.equal(core.tokensAt(200, 2), 200);
  assert.equal(core.tokensAt(null, 1), 0);
});

test("fmtSeconds y fmtInt usan formato es-ES", () => {
  assert.equal(core.fmtSeconds(2.84), "2,8 s");
  assert.equal(core.fmtInt(1234567), "1.234.567");
  assert.equal(core.fmtInt(412), "412");
});

test("prepare valida la forma de los datos", () => {
  assert.equal(core.prepare(null), null);
  assert.equal(core.prepare({}), null);
  assert.equal(core.prepare({ tasks: [], contenders }), null);
  assert.equal(core.prepare({ tasks: [{ results: {} }], contenders }), null);
});

test("prepare toma la primera tarea y los contendientes con resultado (máx. 6)", () => {
  const d = { contenders, tasks: [task(attempt(), attempt({ passed: 6 }), attempt())] };
  const p = core.prepare(d);
  assert.equal(p.sides.length, 3);
  assert.equal(p.sides[1].spec, "replay:beta");
  assert.equal(p.sides[1].passed, 6);
  assert.equal(p.title, "Slugify");
  const many = {};
  const results = {};
  for (const s of "abcdefgh") { many[s] = { spec: s }; results[s] = [attempt()]; }
  assert.equal(core.prepare({ contenders: many, tasks: [{ results }] }).sides.length, 6);
});

test("el veredicto ordena por tests, luego latencia, y marca el glifo con texto", () => {
  const d = { contenders, tasks: [task(attempt({ latency_s: 2.8 }), attempt({ passed: 6, latency_s: 7.6 }), attempt({ latency_s: 0.9 }))] };
  const v = core.verdict(core.prepare(d));
  assert.deepEqual(v.rows.map((r) => r.side), ["c", "a", "b"]);
  assert.equal(v.rows[0].mark, "▲ primero");
  assert.equal(v.rows[1].mark, "✓ resuelve");
  assert.equal(v.rows[2].mark, "✗ falla 2 tests");
  assert.match(v.text, /^En esta tarea \(«Slugify», 1 de 1\), gana C \(replay:gamma\): 8\/8 tests en 0,9 s/);
});

test("si nadie resuelve la tarea, lo dice", () => {
  const bad = attempt({ passed: 3 });
  const v = core.verdict(core.prepare({ contenders, tasks: [task(bad, attempt({ passed: 1 }), bad)] }));
  assert.match(v.text, /^En esta tarea \(«Slugify», 1 de 1\) ninguno resuelve la tarea/);
  assert.equal(v.rows[0].mark, "✗ falla 5 tests");
});

test("el texto no fiable nunca se interpreta como HTML: no hay innerHTML en el script", () => {
  const src = require("node:fs").readFileSync(require.resolve("../../site/demo.js"), "utf8");
  assert.doesNotMatch(src, /innerHTML|outerHTML|insertAdjacentHTML|document\.write|eval\(/);
});

test("el veredicto dice que es solo de una tarea y cuántas tiene el duelo", () => {
  const d = { contenders, tasks: [task(attempt(), attempt(), attempt()), { id: "b" }, { id: "c" }] };
  const v = core.verdict(core.prepare(d));
  assert.match(v.text, /\(«Slugify», 1 de 3\)/);
  assert.equal(core.CAVEAT, "El informe completo agrega todas las tareas y puede dar otro orden.");
});

test("un código largo se recorta avisando y sin partir pares sustitutos", () => {
  const long = "a".repeat(core.MAX_CODE - 1) + "😀" + "b".repeat(50);
  const p = core.prepare({ contenders, tasks: [task(attempt({ code: long }), attempt(), attempt())] });
  const code = p.sides[0].code;
  assert.ok(code.endsWith("\n… (recortado)"));
  const kept = code.slice(0, -"\n… (recortado)".length);
  assert.doesNotMatch(kept, /[\uD800-\uDBFF]$/);
  assert.ok(kept.length <= core.MAX_CODE);
  assert.equal(p.sides[1].code, "x = 1\n", "lo corto no se toca");
});

test("más de 200 tests: se muestran los datos reales y el tope solo acota la lista", () => {
  const big = attempt({ total: 5000, passed: 4990, output: "" });
  const p = core.prepare({ contenders, tasks: [task(big, attempt(), attempt())] });
  const s = p.sides[0];
  assert.equal(s.total, 5000);
  assert.equal(s.passed, 4990);
  assert.equal(s.marks.length, core.MAX_TESTS);
  const v = core.verdict(p);
  assert.equal(v.rows.find((r) => r.side === "a").mark, "✗ falla 10 tests");
});

test("spec, título y enunciado largos se acotan con aviso", () => {
  const t = task(attempt(), attempt(), attempt());
  t.title = "T".repeat(500);
  t.statement = "e".repeat(5000);
  const p = core.prepare({ contenders: { ...contenders, a: { spec: "s".repeat(500) } }, tasks: [t] });
  assert.ok(p.title.length <= 121 && p.title.endsWith("…"));
  assert.ok(p.sides[0].spec.length <= 81 && p.sides[0].spec.endsWith("…"));
  assert.ok(p.statement.endsWith("… (recortado)"));
});
