import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import { issue, parseStrictJson, report, validateRuleRegistry } from "../src/index.js";

const contractRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../src/simplecadapi/scene/contracts",
);

function registry(): Record<string, unknown> {
  return structuredClone(
    parseStrictJson(readFileSync(resolve(contractRoot, "rules/scene-1.0-rules.json"))),
  ) as Record<string, unknown>;
}

function rules(value: Record<string, unknown>): Record<string, unknown>[] {
  assert.ok(Array.isArray(value.rules));
  return value.rules as Record<string, unknown>[];
}

test("rule registry rejects malformed shape, duplicates, and wrong ordering", () => {
  const valid = registry();
  assert.equal(validateRuleRegistry(valid).size, rules(valid).length);

  const missingPrecedence = registry();
  delete rules(missingPrecedence)[0].precedence;
  assert.throws(() => validateRuleRegistry(missingPrecedence), /precedence/);

  const duplicateId = registry();
  rules(duplicateId)[1].id = rules(duplicateId)[0].id;
  assert.throws(() => validateRuleRegistry(duplicateId), /duplicate rule ID/);

  const duplicatePrecedence = registry();
  rules(duplicatePrecedence)[1].precedence = 0;
  assert.throws(() => validateRuleRegistry(duplicatePrecedence), /duplicate precedence/);

  const wrongOrder = registry();
  [rules(wrongOrder)[0], rules(wrongOrder)[1]] = [rules(wrongOrder)[1], rules(wrongOrder)[0]];
  assert.throws(() => validateRuleRegistry(wrongOrder), /ordered by phase and precedence/);

  const wrongIdOrder = registry();
  [rules(wrongIdOrder)[0].id, rules(wrongIdOrder)[1].id] = [rules(wrongIdOrder)[1].id, rules(wrongIdOrder)[0].id];
  assert.throws(() => validateRuleRegistry(wrongIdOrder), /unsigned UTF-8 rule-ID order/);
});

test("registered precedence orders artifact reports", () => {
  const result = report([
    issue("transform_invalid", "/z", "later registered rule"),
    issue("bounds_invalid", "/z", "z message"),
    issue("bounds_invalid", "/z", "a message"),
    issue("bounds_invalid", "/a", "earlier pointer"),
  ], "scene");
  assert.deepEqual(result.issues.map(({ code, path, message }) => [code, path, message]), [
    ["bounds_invalid", "/a", "earlier pointer"],
    ["bounds_invalid", "/z", "a message"],
    ["bounds_invalid", "/z", "z message"],
    ["transform_invalid", "/z", "later registered rule"],
  ]);
});

test("artifact reports reject unregistered, wrong-phase, and wrong-artifact issues", () => {
  assert.throws(
    () => report([issue("not_registered", "", "no authority")], "scene"),
    /unregistered/,
  );
  assert.throws(
    () => report([issue("bounds_invalid", "", "wrong phase", "package")], "scene"),
    /registered phase/,
  );
  assert.throws(
    () => report([issue("presentation_reference_invalid", "", "wrong artifact")], "scene"),
    /does not apply/,
  );
  assert.throws(
    () => report([issue("duplicate_json_key", "/value", "wrong pointer", "parse")], "scene"),
    /root pointer/,
  );
});
