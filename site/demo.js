// Duelo en directo de modelduel: reproduce en el navegador un duelo GRABADO (site/demo/results.json).
// Sin servidor, sin claves y sin ejecutar nada. Vanilla, diferido y sin dependencias.
// El código grabado es dato no fiable: todo se escribe con textContent, nunca como HTML.
(function () {
  "use strict";

  // ---------------------------------------------------------------- lógica pura (probada con node --test)
  var PHASES = [
    { id: "enunciado", end: 3 },
    { id: "escritura", end: 12 },
    { id: "tests", end: 20 },
    { id: "resultado", end: 25 },
  ];
  var DURATION = PHASES[PHASES.length - 1].end;
  var WRITE_S = PHASES[1].end - PHASES[0].end; // lo que tarda el contendiente más lento en escribir
  var MAX_TESTS = 200;
  var MAX_CODE = 4000;
  var MAX_SIDES = 6;
  var SIDES = "abcdef";

  function clamp01(x) {
    return x < 0 ? 0 : x > 1 ? 1 : x;
  }
  function num(x) {
    return typeof x === "number" && isFinite(x) ? x : null;
  }
  function count(x) {
    var n = num(x);
    return n === null || n < 0 ? 0 : Math.floor(n);
  }
  function phaseAt(t) {
    for (var i = 0; i < PHASES.length; i++) if (t <= PHASES[i].end) return i;
    return PHASES.length - 1;
  }
  // Caracteres escritos en el instante t: el más lento (maxLatency) tarda WRITE_S, el resto, en proporción.
  function typedLength(code, t, latency, maxLatency) {
    var lat = num(latency);
    var max = num(maxLatency);
    var dur = lat > 0 && max > 0 ? Math.max(WRITE_S * (lat / max), 0.8) : WRITE_S;
    var frac = clamp01((t - PHASES[0].end) / dur);
    return Math.min(code.length, Math.floor(code.length * frac + 1e-9));
  }
  function tokensAt(total, progress) {
    return Math.round(count(total) * clamp01(progress));
  }
  // Tests resueltos en t: caen uno a uno durante la fase de tests y quedan todos 1 s antes del final.
  function testsDone(total, t) {
    var span = PHASES[2].end - PHASES[1].end - 1;
    return Math.min(total, Math.floor(clamp01((t - PHASES[1].end) / span) * total + 1e-9));
  }
  // Un estado por test, de la línea de progreso de pytest («....FF..»); si no cuadra, passed/total.
  function testMarks(attempt, total) {
    var n = Math.min(count(total), MAX_TESTS);
    var chars = "";
    String(attempt.output || "")
      .split("\n")
      .forEach(function (line) {
        var m = /^([.FEsxX]+)\s*(\[\s*\d+%\])?\s*$/.exec(line);
        if (m) chars += m[1];
      });
    var kinds = { ".": "pass", F: "fail", E: "fail", s: "skip", x: "skip", X: "skip" };
    var marks = [];
    var passed = Math.min(count(attempt.passed), n);
    // Solo se fía de la línea de progreso si cuadra con total y passed.
    if (chars.length === n && chars.split(".").length - 1 === passed) {
      for (var i = 0; i < n; i++) marks.push(kinds[chars[i]]);
      return marks;
    }
    for (var j = 0; j < n; j++) marks.push(j < passed ? "pass" : "fail");
    return marks;
  }
  function fmtSeconds(s) {
    var n = num(s);
    return n === null ? "sin datos" : n.toFixed(1).replace(".", ",") + " s";
  }
  function fmtInt(n) {
    var s = String(count(n));
    return s.length > 4 ? s.replace(/\B(?=(\d{3})+(?!\d))/g, ".") : s;
  }

  // Valida los datos (no fiables) y los reduce a lo que se reproduce: la primera tarea del duelo.
  function prepare(data) {
    if (!data || typeof data !== "object" || !Array.isArray(data.tasks) || !data.tasks.length) return null;
    var task = data.tasks[0];
    if (!task || typeof task !== "object" || !task.results || typeof task.results !== "object") return null;
    var contenders = data.contenders && typeof data.contenders === "object" ? data.contenders : {};
    var sides = [];
    for (var i = 0; i < SIDES.length && sides.length < MAX_SIDES; i++) {
      var side = SIDES[i];
      var attempts = task.results[side];
      if (!Array.isArray(attempts) || !attempts[0] || typeof attempts[0] !== "object") continue;
      var a = attempts[0];
      var total = count(a.total) || count(task.tests_expected);
      var marks = testMarks(a, total);
      var meta = contenders[side] && typeof contenders[side] === "object" ? contenders[side] : {};
      sides.push({
        side: side,
        spec: String(meta.spec || side),
        code: String(a.code || "").slice(0, MAX_CODE),
        latency: num(a.latency_s),
        tokensIn: count(a.input_tokens),
        tokensOut: count(a.output_tokens),
        total: marks.length,
        passed: Math.min(count(a.passed), marks.length),
        marks: marks,
      });
    }
    if (!sides.length) return null;
    var maxLatency = Math.max.apply(
      null,
      sides.map(function (s) {
        return s.latency || 0;
      })
    );
    return {
      title: String(task.title || task.id || "Tarea"),
      statement: String(task.statement || "").slice(0, 1500),
      sides: sides,
      maxLatency: maxLatency,
    };
  }

  // Marcador final: más tests, luego menos latencia. Cada fila lleva glifo y texto, nunca solo color.
  function verdict(plan) {
    var rows = plan.sides
      .map(function (s) {
        return { side: s.side, spec: s.spec, passed: s.passed, total: s.total, latency: s.latency };
      })
      .sort(function (x, y) {
        return (
          y.passed - x.passed ||
          (x.latency === null ? Infinity : x.latency) - (y.latency === null ? Infinity : y.latency) ||
          (x.side < y.side ? -1 : 1)
        );
      });
    rows.forEach(function (r, i) {
      var solved = r.total > 0 && r.passed === r.total;
      var missing = r.total - r.passed;
      r.mark = solved
        ? i === 0
          ? "▲ gana"
          : "✓ resuelve"
        : "✗ falla " + missing + (missing === 1 ? " test" : " tests");
    });
    var top = rows[0];
    var who = top.side.toUpperCase() + " (" + top.spec + ")";
    var text =
      top.total > 0 && top.passed === top.total
        ? "Gana " + who + ": " + top.passed + "/" + top.total + " tests en " + fmtSeconds(top.latency) + ". Resultado pregrabado."
        : "Ninguno resuelve la tarea; el más cercano es " + who + " con " + top.passed + "/" + top.total + " tests. Resultado pregrabado.";
    return { rows: rows, text: text };
  }

  var core = {
    PHASES: PHASES, DURATION: DURATION, WRITE_S: WRITE_S, MAX_TESTS: MAX_TESTS,
    phaseAt: phaseAt, typedLength: typedLength, tokensAt: tokensAt, testsDone: testsDone,
    testMarks: testMarks, fmtSeconds: fmtSeconds, fmtInt: fmtInt, prepare: prepare, verdict: verdict,
  };
  if (typeof module !== "undefined" && module.exports) module.exports = core;
  if (typeof document === "undefined") return;

  // ---------------------------------------------------------------- interfaz
  var root = document.getElementById("demo");
  if (!root) return;
  var $ = function (sel) {
    return root.querySelector(sel);
  };
  var main = $("#demo-main"), stopBtn = $("#demo-stop"), live = $("#demo-live"), clock = $("#demo-clock");
  var stage = $("#demo-stage"), errorBox = $("#demo-error");
  var reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
  var PHASE_TEXT = [
    "Fase 1 de 4: el enunciado de la tarea.",
    "Fase 2 de 4: cada modelo escribe su código grabado.",
    "Fase 3 de 4: se ejecutan los tests.",
    "Fase 4 de 4: marcador final.",
  ];
  var GLYPH = { pass: "✓", fail: "✗", skip: "–" };
  var WORD = { pass: "pasa", fail: "falla", skip: "omitido" };
  var plan = null, result = null, view = null;
  var state = "idle", t = 0, timer = null, last = 0, lastPhase = -1, loading = false;

  function el(tag, cls, text) {
    var node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function setText(node, text) {
    if (node.textContent !== text) node.textContent = text;
  }
  function mmss(s) {
    s = Math.floor(s);
    return "0" + Math.floor(s / 60) + ":" + (s % 60 < 10 ? "0" : "") + (s % 60);
  }

  function build() {
    stage.replaceChildren();
    var head = el("div", "demo-task");
    head.appendChild(el("h3", "", plan.title));
    var statement = el("pre", "demo-statement", plan.statement);
    statement.tabIndex = 0;
    statement.setAttribute("aria-label", "Enunciado de la tarea");
    head.appendChild(statement);
    var grid = el("div", "demo-grid");
    grid.hidden = true;
    var panels = plan.sides.map(function (s) {
      var panel = el("article", "demo-panel " + s.side);
      var title = el("h4", "demo-who");
      title.appendChild(el("span", "tag", s.side.toUpperCase()));
      title.appendChild(el("span", "", s.spec));
      var code = el("pre", "demo-code");
      code.tabIndex = 0;
      code.setAttribute("aria-label", "Código de " + s.side.toUpperCase());
      var tokens = el("p", "demo-tokens");
      var list = el("ol", "demo-tests");
      var items = s.marks.map(function (_m, i) {
        var li = el("li", "", "· test " + (i + 1));
        list.appendChild(li);
        return li;
      });
      var label = el("p", "demo-count");
      var bar = el("div", "demo-bar");
      var fill = el("div", "demo-fill");
      bar.appendChild(fill);
      [title, code, tokens, list, label, bar].forEach(function (n) {
        panel.appendChild(n);
      });
      grid.appendChild(panel);
      return { s: s, code: code, tokens: tokens, items: items, label: label, fill: fill, typed: -1, done: -1 };
    });
    result = verdict(plan);
    var box = el("div", "demo-result");
    box.hidden = true;
    box.appendChild(el("h3", "", "Marcador"));
    var rows = el("ol", "demo-board");
    result.rows.forEach(function (r) {
      var li = el("li", r.side);
      li.appendChild(el("span", "tag", r.side.toUpperCase()));
      li.appendChild(
        el("span", "", r.spec + " · " + r.passed + "/" + r.total + " tests · " + fmtSeconds(r.latency) + " · " + r.mark)
      );
      rows.appendChild(li);
    });
    box.appendChild(rows);
    box.appendChild(el("p", "demo-verdict", result.text));
    var more = el("p", "demo-more");
    var link = el("a", "btn", "Ver el informe completo");
    link.href = "demo/";
    more.appendChild(link);
    box.appendChild(more);
    [head, grid, box].forEach(function (n) {
      stage.appendChild(n);
    });
    view = { grid: grid, panels: panels, box: box };
    lastPhase = -1;
  }

  function render() {
    var ph = phaseAt(t);
    if (ph !== lastPhase) {
      lastPhase = ph;
      setText(live, PHASE_TEXT[ph] + (ph === 3 ? " " + result.text : ""));
    }
    setText(clock, mmss(t) + " / " + mmss(DURATION));
    view.grid.hidden = t <= PHASES[0].end;
    view.box.hidden = t <= PHASES[2].end;
    view.panels.forEach(function (p) {
      var s = p.s;
      var n = typedLength(s.code, t, s.latency, plan.maxLatency);
      if (n !== p.typed) {
        p.typed = n;
        p.code.textContent = s.code.slice(0, n);
        p.code.scrollTop = p.code.scrollHeight;
      }
      var progress = s.code.length ? n / s.code.length : t > PHASES[0].end ? 1 : 0;
      setText(
        p.tokens,
        "Tokens: entrada " + fmtInt(s.tokensIn) + " · salida " + fmtInt(tokensAt(s.tokensOut, progress)) + " de " + fmtInt(s.tokensOut)
      );
      var done = testsDone(s.total, t);
      if (done !== p.done) {
        p.done = done;
        var passed = 0;
        p.items.forEach(function (li, i) {
          var kind = s.marks[i];
          if (i < done) {
            if (kind === "pass") passed++;
            li.textContent = GLYPH[kind] + " test " + (i + 1) + " " + WORD[kind];
            li.className = kind;
          } else {
            li.textContent = "· test " + (i + 1);
            li.className = "";
          }
        });
        p.fill.style.width = (s.total ? (passed / s.total) * 100 : 0) + "%";
        p.label.textContent = passed + "/" + s.total + " tests superados";
      }
    });
  }

  function label() {
    var text = {
      idle: "Ver un duelo en directo",
      running: "Pausar",
      paused: "Reanudar",
      manual: "Siguiente",
      done: "Ver otra vez",
    }[state];
    setText(main, text);
    stopBtn.hidden = state === "idle";
  }
  function stopTimer() {
    if (timer !== null) clearInterval(timer);
    timer = null;
  }
  function tick() {
    var now = performance.now();
    t += Math.min((now - last) / 1000, 0.5);
    last = now;
    if (t >= DURATION) {
      t = DURATION;
      stopTimer();
      state = "done";
      label();
    }
    render();
  }
  function run() {
    last = performance.now();
    timer = setInterval(tick, 100);
    state = "running";
    label();
  }
  function pause() {
    stopTimer();
    state = "paused";
    label();
  }
  function begin() {
    build();
    stage.hidden = false;
    if (reduce.matches) {
      t = PHASES[0].end;
      state = "manual";
      label();
      render();
    } else {
      t = 0;
      render();
      run();
    }
  }
  function next() {
    var i = Math.min(phaseAt(t) + 1, PHASES.length - 1);
    t = PHASES[i].end;
    if (i === PHASES.length - 1) state = "done";
    label();
    render();
  }
  function stop() {
    stopTimer();
    stage.replaceChildren();
    stage.hidden = true;
    state = "idle";
    t = 0;
    setText(clock, "");
    setText(live, "Duelo detenido.");
    label();
  }
  function load() {
    if (loading) return;
    loading = true;
    main.setAttribute("aria-busy", "true"); // sin disabled: así el foco no se pierde
    errorBox.hidden = true;
    fetch("demo/results.json", { cache: "no-cache" })
      .then(function (r) {
        if (!r.ok) throw new Error("HTTP " + r.status);
        return r.json();
      })
      .then(function (data) {
        plan = prepare(data);
        if (!plan) throw new Error("formato inesperado");
        begin();
      })
      .catch(function () {
        errorBox.textContent = "No se pudo cargar el duelo pregrabado. Puedes ver el informe estático.";
        errorBox.hidden = false;
      })
      .then(function () {
        loading = false;
        main.removeAttribute("aria-busy");
      });
  }

  main.addEventListener("click", function () {
    if (state === "idle") return plan ? begin() : load();
    if (state === "running") return pause();
    if (state === "paused") return (last = performance.now()), run();
    if (state === "manual") return next();
    if (state === "done") return begin();
  });
  stopBtn.addEventListener("click", stop);
  document.addEventListener("visibilitychange", function () {
    if (document.hidden && state === "running") pause();
  });

  // Con JavaScript: se muestran los controles y se oculta el enlace de respaldo.
  var nojs = $(".demo-nojs");
  if (nojs) nojs.hidden = true;
  $(".demo-controls").hidden = false;
  label();
})();
