import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import test from "node:test";
import {
  ConnectorBindingDocument,
  ContractDocumentValidationError,
  EntityDocument,
  type ImmutableContractDocument,
  NormalizedProductDocument,
  parseCanonicalJson,
  parseStrictJson,
  PresentationDocument,
  SceneDocument,
  sha256,
} from "../src/index.js";

interface ValidationCase {
  valid: boolean;
  payload_base64: string;
}

interface Corpus {
  artifacts: Record<string, { base64: string }>;
  presentation_cases: ValidationCase[];
  connector_binding_cases: ValidationCase[];
  normalized_product_cases: ValidationCase[];
}

interface TestFactory {
  fromValue(value: unknown): ImmutableContractDocument<unknown>;
  parse(data: Uint8Array | string): ImmutableContractDocument<unknown>;
}

const here = dirname(fileURLToPath(import.meta.url));
const corpus = parseStrictJson(
  readFileSync(resolve(here, "../../../test/fixtures/scene-contract/corpus.json")),
) as Corpus;

const validCase = (cases: ValidationCase[]): Buffer => {
  const item = cases.find((candidate) => candidate.valid);
  assert.ok(item !== undefined);
  return Buffer.from(item.payload_base64, "base64");
};

const documents: readonly [string, TestFactory, Buffer][] = [
  [
    "scene",
    SceneDocument as unknown as TestFactory,
    Buffer.from(corpus.artifacts.scene.base64, "base64"),
  ],
  [
    "entities",
    EntityDocument as unknown as TestFactory,
    Buffer.from(corpus.artifacts.entities.base64, "base64"),
  ],
  [
    "presentation",
    PresentationDocument as unknown as TestFactory,
    validCase(corpus.presentation_cases),
  ],
  [
    "connector binding",
    ConnectorBindingDocument as unknown as TestFactory,
    validCase(corpus.connector_binding_cases),
  ],
  [
    "normalized product",
    NormalizedProductDocument as unknown as TestFactory,
    validCase(corpus.normalized_product_cases),
  ],
];

function record(value: unknown): Record<string, unknown> {
  assert.ok(value !== null && typeof value === "object" && !Array.isArray(value));
  return value as Record<string, unknown>;
}

function assertDeepFrozen(value: unknown): void {
  if (value === null || typeof value !== "object") return;
  assert.equal(Object.isFrozen(value), true);
  for (const child of Object.values(value)) assertDeepFrozen(child);
}

function nestedContainer(value: Record<string, unknown>): Record<string, unknown> | unknown[] {
  const result = Object.values(value).find(
    (child) => child !== null && typeof child === "object",
  );
  assert.ok(result !== undefined);
  return result as Record<string, unknown> | unknown[];
}

test("all contract document factories construct, parse, validate, and round trip", () => {
  for (const [name, factory, payload] of documents) {
    const input = record(parseCanonicalJson(payload));
    const constructed = factory.fromValue(input);
    const parsed = factory.parse(payload);

    assert.deepEqual(constructed.canonicalBytes, payload, name);
    assert.deepEqual(parsed.canonicalBytes, payload, name);
    assert.equal(constructed.canonicalHash, sha256(payload), name);
    assert.deepEqual(constructed.toMutable(), parsed.toMutable(), name);
    assert.deepEqual(factory.fromValue(constructed.value).canonicalBytes, payload, name);
  }
});

test("contract documents resist nested mutation and isolate mutable copies", () => {
  for (const [name, factory, payload] of documents) {
    const input = record(parseCanonicalJson(payload));
    const document = factory.fromValue(input);
    const expectedHash = document.canonicalHash;
    const expectedBytes = document.canonicalBytes;

    assert.equal(Object.isFrozen(document), true, name);
    assertDeepFrozen(document.value);
    assert.throws(() => {
      record(document.value).mutation = true;
    }, TypeError, name);
    const frozenNested = nestedContainer(record(document.value));
    assert.throws(() => {
      if (Array.isArray(frozenNested)) frozenNested.push(null);
      else frozenNested.mutation = true;
    }, TypeError, name);

    input.mutation = true;
    const firstCopy = record(document.toMutable());
    const secondCopy = record(document.toMutable());
    const mutableNested = nestedContainer(firstCopy);
    if (Array.isArray(mutableNested)) mutableNested.push(null);
    else mutableNested.mutation = true;
    firstCopy.mutation = true;

    assert.equal(Object.hasOwn(record(document.value), "mutation"), false, name);
    assert.equal(Object.hasOwn(secondCopy, "mutation"), false, name);
    assert.notDeepEqual(firstCopy, secondCopy, name);

    const exposedBytes = document.canonicalBytes;
    exposedBytes[0] ^= 0xff;
    assert.deepEqual(document.canonicalBytes, expectedBytes, name);
    assert.equal(document.canonicalHash, expectedHash, name);
  }
});

test("document constructors reject invalid values, noncanonical input, and stale revisions", () => {
  for (const [name, factory] of documents) {
    assert.throws(
      () => factory.fromValue({}),
      ContractDocumentValidationError,
      name,
    );
  }
  assert.throws(() => SceneDocument.parse('{ "schema_version": "1.0" }'), /canonical/);

  const scene = record(
    parseCanonicalJson(Buffer.from(corpus.artifacts.scene.base64, "base64")),
  );
  scene.revision = `sha256:${"0".repeat(64)}`;
  assert.throws(
    () => SceneDocument.fromValue(scene as never),
    (error: unknown) =>
      error instanceof ContractDocumentValidationError &&
      error.report.firstError?.code === "revision_mismatch",
  );
});
