import { test } from "node:test";
import assert from "node:assert/strict";
import { formatBytes } from "./solution.mjs";

test("bytes sin decimales", () => {
  assert.equal(formatBytes(512), "512 B");
  assert.equal(formatBytes(0), "0 B");
});

test("kilobytes usan coma decimal", () => {
  assert.equal(formatBytes(1536), "1,5 KiB");
});

test("quita ceros finales", () => {
  assert.equal(formatBytes(1024, 3), "1 KiB");
  assert.equal(formatBytes(2560, 2), "2,5 KiB");
});

test("respeta el número de decimales", () => {
  assert.equal(formatBytes(1234, 2), "1,21 KiB");
});

test("usa unidades grandes", () => {
  assert.equal(formatBytes(1048576), "1 MiB");
  assert.equal(formatBytes(1073741824), "1 GiB");
  assert.equal(formatBytes(1099511627776), "1 TiB");
});

test("conserva el signo negativo", () => {
  assert.equal(formatBytes(-2048, 0), "-2 KiB");
});

test("rechaza números no finitos", () => {
  assert.throws(() => formatBytes(Number.NaN), TypeError);
  assert.throws(() => formatBytes(Number.POSITIVE_INFINITY), TypeError);
  assert.throws(() => formatBytes(Number.NEGATIVE_INFINITY), TypeError);
});

test("los valores menores que un kibibyte siguen en bytes", () => {
  assert.equal(formatBytes(1023), "1023 B");
});
