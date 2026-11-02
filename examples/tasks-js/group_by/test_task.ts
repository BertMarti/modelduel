import { test } from "node:test";
import assert from "node:assert/strict";
import { groupBy } from "./solution.ts";

// Se comparan las propiedades, no el prototipo: `Object.groupBy` devuelve un objeto sin
// prototipo y también vale.
function plano<T extends object>(objeto: T): T {
  return { ...objeto };
}

test("agrupa cadenas por su primera letra", () => {
  const grupos = groupBy(["ana", "alba", "bruno"], (nombre) => nombre[0]);
  assert.deepEqual(plano(grupos), { a: ["ana", "alba"], b: ["bruno"] });
});

test("conserva el orden dentro de cada grupo", () => {
  const grupos = groupBy([3, 1, 4, 2, 5], (numero) => numero % 2);
  assert.deepEqual(plano(grupos), { 0: [4, 2], 1: [3, 1, 5] });
});

test("devuelve un objeto vacío para una lista vacía", () => {
  assert.deepEqual(plano(groupBy<number, number>([], (valor) => valor)), {});
});

test("no modifica la entrada", () => {
  const entrada = [
    { grupo: "b", valor: 2 },
    { grupo: "a", valor: 1 },
    { grupo: "b", valor: 3 },
  ];
  const copia = structuredClone(entrada);
  groupBy(entrada, (elemento) => elemento.grupo);
  assert.deepEqual(entrada, copia);
});

test("admite claves numéricas", () => {
  const grupos = groupBy([1, 2, 3, 4], (numero) => numero % 2);
  assert.deepEqual(plano(grupos), { 0: [2, 4], 1: [1, 3] });
});

test("crea un grupo separado para cada clave", () => {
  const grupos = groupBy(["a", "b", "c"], (letra) => letra);
  assert.deepEqual(plano(grupos), { a: ["a"], b: ["b"], c: ["c"] });
});

test("conserva objetos completos en los grupos", () => {
  const uno = { tipo: "fruta", nombre: "pera" };
  const dos = { tipo: "verdura", nombre: "puerro" };
  const grupos = groupBy([uno, dos], (elemento) => elemento.tipo);
  assert.equal(grupos.fruta[0], uno);
  assert.deepEqual(plano(grupos), { fruta: [uno], verdura: [dos] });
});

test("rechaza una clave que no es función", () => {
  assert.throws(() => groupBy([1, 2], 7 as unknown as (item: number) => number), TypeError);
});
