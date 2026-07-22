import assert from "node:assert/strict";
import test from "node:test";
import {
  canonicalJsonBytes,
  parseCanonicalJson,
  parseStrictJson,
  validateNormalizedProduct,
  withSceneRevision,
} from "../src/index.js";

test("canonical JSON renders finite Numbers from their value", () => {
  assert.equal(canonicalJsonBytes(1e30).toString("utf8"), "1e+30");
  assert.equal(canonicalJsonBytes(parseStrictJson("1e30")).toString("utf8"), "1e+30");

  const nested = parseStrictJson('{"large":1e30,"small":[1E-7]}');
  assert.equal(
    canonicalJsonBytes(nested).toString("utf8"),
    '{"large":1e+30,"small":[1e-7]}',
  );
  assert.deepEqual(parseCanonicalJson("1e+30"), 1e30);
  assert.throws(() => parseCanonicalJson("1e30"), /canonical/);
});

test("canonical JSON normalizes negative zero at root and nested positions", () => {
  const root = parseStrictJson("-0");
  assert.equal(Object.is(root, -0), true);
  assert.equal(canonicalJsonBytes(root).toString("utf8"), "0");

  const nested = parseStrictJson('{"values":[-0,0e0]}');
  assert.equal(canonicalJsonBytes(nested).toString("utf8"), '{"values":[0,0]}');
  assert.throws(() => parseCanonicalJson("-0"), /canonical/);
});

test("cloning parsed values does not change canonical bytes or scene revision", () => {
  const scene = parseStrictJson('{"measurement":1e30,"nested":{"epsilon":1e-7}}') as Record<
    string,
    unknown
  >;
  const clone = structuredClone(scene);

  assert.deepEqual(canonicalJsonBytes(clone), canonicalJsonBytes(scene));
  assert.deepEqual(withSceneRevision(clone), withSceneRevision(scene));
});

test("unsafe integer JSON is rejected lexically without affecting exponent Numbers", () => {
  assert.throws(() => parseStrictJson("9007199254740992"), /safe domain/);
  assert.throws(() => parseStrictJson('{"value":-9007199254740992}'), /safe domain/);
  assert.equal(
    canonicalJsonBytes(Number.MAX_SAFE_INTEGER + 1).toString("utf8"),
    "9007199254740992",
  );
  assert.equal(canonicalJsonBytes(parseStrictJson("1e30")).toString("utf8"), "1e+30");
});

test("strict JSON rejects unpaired surrogates in values and object keys", () => {
  assert.throws(() => parseStrictJson('{"value":"\\ud800"}'), /surrogate/);
  assert.throws(() => parseStrictJson('{"\\ud800":0}'), /surrogate/);
});

test("serialized JSON over the depth limit reports a budget issue", () => {
  let serialized = "0";
  for (let depth = 0; depth < 65; depth += 1) serialized = `{"x":${serialized}}`;

  const result = validateNormalizedProduct(serialized);
  assert.equal(result.firstError?.code, "resource_limit_exceeded");
  assert.equal(result.firstError?.phase, "budget");
  assert.equal(result.firstError?.path, "/x".repeat(65));
});

test("serialized non-finite tokens and overflow report nonfinite_json_number", () => {
  for (const serialized of [
    "NaN",
    "Infinity",
    "-Infinity",
    "1e999",
    '[0,NaN]',
    '{"value":1e999}',
  ]) {
    const result = validateNormalizedProduct(serialized);
    assert.equal(result.firstError?.code, "nonfinite_json_number", serialized);
    assert.equal(result.firstError?.phase, "parse", serialized);
  }

  const programmatic = validateNormalizedProduct({ metadata: { value: Number.NaN } });
  assert.equal(programmatic.firstError?.code, "nonfinite_json_number");
  assert.equal(programmatic.firstError?.path, "/metadata/value");
});
