// Interfaz de site/demo.js con un DOM de mentira (sin dependencias).
const test = require("node:test");
const assert = require("node:assert/strict");

const ctx = {};

class El {
  constructor(tag) {
    this.tag = tag;
    this.children = [];
    this.attrs = {};
    this.handlers = {};
    this.style = {};
    this.className = "";
    this._text = "";
    this._hidden = false;
    this.tabIndex = -1;
    this.scrollTop = 0;
    this.scrollHeight = 0;
  }
  get hidden() {
    return this._hidden;
  }
  set hidden(v) {
    this._hidden = !!v;
    // Como un navegador: un elemento oculto no puede tener el foco.
    if (v && ctx.doc && ctx.doc.activeElement === this) ctx.doc.activeElement = ctx.doc.body;
  }
  get textContent() {
    return this._text;
  }
  set textContent(v) {
    this._text = String(v);
    this.children = [];
  }
  setAttribute(k, v) {
    this.attrs[k] = String(v);
  }
  removeAttribute(k) {
    delete this.attrs[k];
  }
  appendChild(c) {
    this.children.push(c);
    return c;
  }
  replaceChildren() {
    this.children = [];
  }
  addEventListener(t, f) {
    (this.handlers[t] = this.handlers[t] || []).push(f);
  }
  focus() {
    if (!this._hidden) ctx.doc.activeElement = this;
  }
  click() {
    this.focus(); // un clic real enfoca el botón
    (this.handlers.click || []).forEach((f) => f());
  }
  find(pred, out = []) {
    if (pred(this)) out.push(this);
    this.children.forEach((c) => c.find(pred, out));
    return out;
  }
}

function setup({ reduce = false, hidden = false } = {}) {
  const ids = {};
  for (const id of ["demo-main", "demo-stop", "demo-live", "demo-clock", "demo-stage", "demo-error"]) {
    ids[id] = new El("x");
  }
  ids["demo-stop"].hidden = true;
  const controls = new El("div");
  controls.hidden = true;
  const nojs = new El("p");
  const rootEl = new El("section");
  rootEl.querySelector = (sel) =>
    sel.startsWith("#") ? ids[sel.slice(1)] : sel === ".demo-controls" ? controls : nojs;
  const doc = {
    body: new El("body"),
    hidden,
    activeElement: null,
    listeners: {},
    getElementById: (id) => (id === "demo" ? rootEl : null),
    createElement: (t) => new El(t),
    addEventListener(t, f) {
      (this.listeners[t] = this.listeners[t] || []).push(f);
    },
  };
  doc.activeElement = doc.body;
  ctx.doc = doc;
  const data = {
    contenders: { a: { spec: "replay:alfa" }, b: { spec: "replay:beta" } },
    tasks: [
      {
        title: "Slugify",
        statement: "x",
        tests_expected: 2,
        results: {
          a: [{ passed: 2, total: 2, latency_s: 1, code: "a = 1", output: ".." }],
          b: [{ passed: 1, total: 2, latency_s: 2, code: "b = 2", output: ".F" }],
        },
      },
    ],
  };
  Object.assign(globalThis, {
    document: doc,
    window: { matchMedia: () => ({ matches: reduce }) },
    performance: { now: () => 0 },
    setInterval: () => 1, // sin temporizadores reales: el reloj no avanza solo
    clearInterval: () => {},
    fetch: async () => ({ ok: true, json: async () => data }),
  });
  delete require.cache[require.resolve("../../site/demo.js")];
  require("../../site/demo.js");
  return { ids, controls, nojs, doc };
}
const flush = () => new Promise((r) => setTimeout(r, 20));

test("al cargar se muestran los controles y se oculta el respaldo sin JS", () => {
  const { controls, nojs } = setup();
  assert.equal(controls.hidden, false);
  assert.equal(nojs.hidden, true);
});

test("Detener devuelve el foco al botón principal (no cae en body)", async () => {
  const { ids, doc } = setup();
  ids["demo-main"].click();
  await flush();
  assert.equal(ids["demo-main"].textContent, "Pausar");
  assert.equal(ids["demo-stop"].hidden, false);
  ids["demo-stop"].click(); // el foco estaba en Detener y label() lo oculta
  assert.equal(ids["demo-stop"].hidden, true);
  assert.equal(doc.activeElement, ids["demo-main"]);
  assert.equal(ids["demo-main"].textContent, "Ver un duelo en directo");
});

test("el fallo de carga se muestra y el botón sigue disponible", async () => {
  const { ids } = setup();
  globalThis.fetch = async () => {
    throw new Error("sin red");
  };
  ids["demo-main"].click();
  await flush();
  assert.equal(ids["demo-error"].hidden, false);
  assert.match(ids["demo-error"].textContent, /No se pudo cargar/);
  assert.equal(ids["demo-main"].attrs["aria-busy"], undefined);
});

test("si la pestaña está oculta al empezar, el duelo arranca en pausa", async () => {
  const { ids } = setup({ hidden: true });
  ids["demo-main"].click();
  await flush();
  assert.equal(ids["demo-main"].textContent, "Reanudar");
  ids["demo-stop"].click();
});

test("el veredicto visible incluye la salvedad del informe completo", async () => {
  const { ids } = setup({ reduce: true });
  ids["demo-main"].click();
  await flush();
  for (let i = 0; i < 3; i++) ids["demo-main"].click(); // Siguiente x3 hasta el marcador
  const texts = ids["demo-stage"].find(() => true).map((e) => e.textContent);
  assert.ok(texts.some((t) => t.includes("El informe completo agrega todas las tareas y puede dar otro orden.")));
  assert.ok(texts.some((t) => t.startsWith("En esta tarea («Slugify», 1 de 1), gana A")));
});

test("los <pre> enfocables son grupos con etiqueta", async () => {
  const { ids } = setup({ reduce: true });
  ids["demo-main"].click();
  await flush();
  const pres = ids["demo-stage"].find((e) => e.tag === "pre");
  assert.ok(pres.length >= 3);
  for (const p of pres) {
    assert.equal(p.attrs.role, "group");
    assert.ok(p.attrs["aria-label"]);
    assert.equal(p.tabIndex, 0);
  }
});
