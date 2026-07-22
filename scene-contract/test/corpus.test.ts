import { createHash } from "node:crypto";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import assert from "node:assert/strict";
import test, { type TestContext } from "node:test";
import {
  canonicalJsonBytes,
  canonicalZipBytes,
  BASE_LIMITS,
  computeSceneRevision,
  DuplicateKeyError,
  parseCanonicalJson,
  parseStrictJson,
  preflightAggregateCompressionRatio,
  preflightArchiveMemberSizes,
  preflightGlb,
  preflightGlbCounts,
  preflightInputArchiveSize,
  preflightMemberCompressionRatio,
  preflightZipBytes,
  profileCross,
  profileF32Bits,
  profileNormalize,
  issue,
  report,
  sha256,
  validateConnectorBinding,
  validateEntityAsset,
  validateNormalizedProduct,
  validatePresentation,
  validateSceneManifest,
  validateScenePackage,
  computePackageBudgetTotals,
  jsonResourceIssues,
  packageBudgetIssues,
  resourceCountIssues,
  withSceneRevision,
  type SceneResourceLimits,
} from "../src/index.js";
import { validateSceneSchema, validateSchemaPointer, type SchemaArtifact } from "../src/schema.js";
import {
  applySceneFieldCase,
  corpusBlobs,
  sceneShapeFacts,
  type ExpectedIssue,
  type PackageCase,
  type SceneFieldCase,
  type SceneShapeCase,
} from "./corpus-support.js";

interface ValidationCase { name: string; valid: boolean; expected: ExpectedIssue | null; payload_base64: string }
interface GlbCase { name: string; valid: boolean; error: string | null; expected_kind: "triangle" | "line"; kind: "triangle" | "line" | null; payload_base64: string }
interface ZipCase { name: string; valid: boolean; error: string | null; used_deflate: boolean | null; payload_base64: string }
interface NumericVector { name: string; operation: "f32" | "cross" | "normalize"; input_bits: string[] | string[][]; expected_bits?: string | string[]; error?: string; valid: boolean }
interface ResourceCase { name: string; operation: string; parameters: Record<string, unknown>; valid: boolean; error?: string | null; expected?: ExpectedIssue | null }
interface Artifact { base64: string; sha256: string; uri?: string; revision?: string }
interface RevisionVector { name: string; canonical_base64: string; draft_base64: string; revision: string; sha256: string }
interface SchemaMutation { operation: "delete" | "set"; path: (string | number)[]; value?: unknown }
interface SchemaFieldMatrix {
  artifact: SchemaArtifact;
  base: Record<string, unknown>;
  cases: { mutations: SchemaMutation[]; name: string; valid: boolean }[];
  schema_pointer: string;
  variant: string;
}
interface Corpus {
  format_version: string;
  artifacts: Record<string, Artifact>;
  blobs: Record<string, string>;
  jcs_vectors: { name: string; input: unknown; canonical_base64: string; sha256: string }[];
  manifest_cases: ValidationCase[];
  entity_cases: ValidationCase[];
  presentation_cases: ValidationCase[];
  connector_binding_cases: ValidationCase[];
  normalized_product_cases: ValidationCase[];
  package_cases: PackageCase[];
  glb_cases: GlbCase[];
  numeric_vectors: NumericVector[];
  resource_cases: ResourceCase[];
  resource_limits: Record<string, number>;
  revision_vectors: RevisionVector[];
  scene_field_cases: SceneFieldCase[];
  scene_shape_cases: SceneShapeCase[];
  schema_field_matrices: SchemaFieldMatrix[];
  zip_cases: ZipCase[];
}

const here = dirname(fileURLToPath(import.meta.url));
const corpusPath = resolve(here, "../../../test/fixtures/scene-contract/corpus.json");
const corpus = parseStrictJson(readFileSync(corpusPath)) as Corpus;
const decode = (value: string) => Buffer.from(value, "base64");

test("shared corpus has every Scene 1.0 parity section", () => {
  assert.equal(corpus.format_version, "1.0");
  for (const section of [
    corpus.jcs_vectors,
    corpus.manifest_cases,
    corpus.entity_cases,
    corpus.presentation_cases,
    corpus.connector_binding_cases,
    corpus.normalized_product_cases,
    corpus.package_cases,
    corpus.glb_cases,
    corpus.numeric_vectors,
    corpus.resource_cases,
    corpus.revision_vectors,
    corpus.scene_field_cases,
    corpus.scene_shape_cases,
    corpus.schema_field_matrices,
    corpus.zip_cases,
  ]) assert.ok(section.length > 0);
});

function applySchemaMutations(base: Record<string, unknown>, mutations: SchemaMutation[]): Record<string, unknown> {
  const result = structuredClone(base);
  for (const mutation of mutations) {
    let current: Record<string | number, unknown> = result;
    for (const part of mutation.path.slice(0, -1)) current = current[part] as Record<string | number, unknown>;
    const field = mutation.path.at(-1)!;
    if (mutation.operation === "delete") delete current[field];
    else current[field] = structuredClone(mutation.value);
  }
  return result;
}

test("all closed schema records and discriminator variants replay shared field matrices", async (context) => {
  for (const matrix of corpus.schema_field_matrices) await context.test(
    `${matrix.artifact}:${matrix.schema_pointer}:${matrix.variant}`,
    async (matrixContext) => {
      for (const item of matrix.cases) await matrixContext.test(item.name, () => {
        const value = applySchemaMutations(matrix.base, item.mutations);
        assert.equal(validateSchemaPointer(matrix.artifact, matrix.schema_pointer, value), item.valid);
      });
    },
  );
});

test("shared positive case names cannot drift to negative expectations", () => {
  const positiveNames: string[] = [];
  for (const [sectionName, value] of Object.entries(corpus)) {
    if (!Array.isArray(value)) continue;
    for (const item of value) {
      if (item === null || typeof item !== "object" || Array.isArray(item)) continue;
      const record = item as Record<string, unknown>;
      if (
        typeof record.name !== "string"
        || (!record.name.startsWith("valid_") && record.name !== "nullable_fields_nonnull")
      ) continue;
      const label = `${sectionName}:${record.name}`;
      positiveNames.push(label);
      assert.equal(record.valid, true, label);
      if (Object.hasOwn(record, "expected")) assert.equal(record.expected, null, label);
      if (Object.hasOwn(record, "error")) assert.equal(record.error, null, label);
    }
  }
  assert.equal(positiveNames.length, 30);
});

test("strict JSON rejects duplicate keys and protects ordinary object semantics", () => {
  assert.throws(() => parseStrictJson(Buffer.from('{"a":1,"a":2}')), DuplicateKeyError);
  const value = parseStrictJson(Buffer.from('{"__proto__":{"polluted":true}}')) as Record<string, unknown>;
  assert.equal(Object.hasOwn(value, "__proto__"), true);
  assert.equal(({} as { polluted?: boolean }).polluted, undefined);
});

test("canonical JSON accepts finite numbers and rejects non-finite numbers", () => {
  assert.equal(canonicalJsonBytes(1e30).toString("utf8"), "1e+30");
  for (const value of [Number.NaN, Number.POSITIVE_INFINITY, Number.NEGATIVE_INFINITY]) {
    assert.throws(() => canonicalJsonBytes(value), /finite/);
  }
  assert.equal(canonicalJsonBytes(1.25).toString("utf8"), "1.25");
});

test("strict parsing accepts valid noncanonical JSON while canonical parsing rejects it", () => {
  const bytes = Buffer.from('{"b":1, "a":2}');
  assert.equal((parseStrictJson(bytes) as Record<string, unknown>).a, 2);
  assert.throws(() => parseCanonicalJson(bytes), /canonical/);
});

test("public validator resource overflows remain budget issues", () => {
  const scene = validScene();
  const sceneBytes = canonicalJsonBytes(scene);
  const collectionResult = validateSceneManifest(scene, { ...BASE_LIMITS, definitions: 0 });
  const serializedResult = validateSceneManifest(scene, {
    ...BASE_LIMITS,
    scene_json_bytes: sceneBytes.length - 1,
  });

  assert.deepEqual(
    collectionResult.firstError === null
      ? null
      : [collectionResult.firstError.code, collectionResult.firstError.phase, collectionResult.firstError.path],
    ["resource_limit_exceeded", "budget", "/definitions"],
  );
  assert.deepEqual(
    serializedResult.firstError === null
      ? null
      : [serializedResult.firstError.code, serializedResult.firstError.phase, serializedResult.firstError.path],
    ["resource_limit_exceeded", "budget", ""],
  );
});

test("reports are deterministic by phase, UTF-8 rule ID, and UTF-8 pointer", () => {
  const result = report([
    issue("z", "/b", "later path", "semantic"),
    issue("a", "/z", "later code", "semantic"),
    issue("a", "/a", "earlier pointer", "semantic"),
    issue("z", "/z", "structure first", "structure"),
    issue("a", "/a", "duplicate is ignored", "semantic"),
  ]);
  assert.deepEqual(
    result.issues.map(({ phase, code, path }) => [phase, code, path]),
    [
      ["structure", "z", "/z"],
      ["semantic", "a", "/a"],
      ["semantic", "a", "/z"],
      ["semantic", "z", "/b"],
    ],
  );
});

test("RFC 8785 vectors reproduce exact bytes and hashes", async (context) => {
  for (const vector of corpus.jcs_vectors) await context.test(vector.name, () => {
    const canonical = canonicalJsonBytes(vector.input);
    assert.deepEqual(canonical, decode(vector.canonical_base64));
    assert.equal(sha256(canonical), vector.sha256);
  });
});

test("scene artifact revision and content hash are exact", () => {
  const bytes = decode(corpus.artifacts.scene.base64);
  const scene = parseStrictJson(bytes) as Record<string, unknown>;
  assert.equal(computeSceneRevision(scene), corpus.artifacts.scene.revision);
  assert.equal(sha256(bytes), corpus.artifacts.scene.sha256);
});

test("all manifest cases match validity and expected first issue", async (context) => {
  for (const item of corpus.manifest_cases) await context.test(item.name, () => {
    const result = validateSceneManifest(decode(item.payload_base64));
    assert.equal(result.valid, item.valid);
    if (item.expected !== null) {
      assert.equal(result.firstError?.code, item.expected.code);
      assert.equal(result.firstError?.path, item.expected.path);
    }
  });
});

test("all entity cases match validity and expected first issue", async (context) => {
  for (const item of corpus.entity_cases) await context.test(item.name, () => {
    const result = validateEntityAsset(decode(item.payload_base64));
    assert.equal(result.valid, item.valid);
    if (item.expected !== null) {
      assert.equal(result.firstError?.code, item.expected.code);
      assert.equal(result.firstError?.path, item.expected.path);
    }
  });
});

async function assertValidationCases(
  context: TestContext,
  cases: ValidationCase[],
  validate: (value: unknown) => ReturnType<typeof validateSceneManifest>,
): Promise<void> {
  for (const item of cases) await context.test(item.name, () => {
    const result = validate(decode(item.payload_base64));
    assert.equal(result.valid, item.valid);
    if (item.expected !== null) {
      assert.equal(result.firstError?.code, item.expected.code);
      assert.equal(result.firstError?.path, item.expected.path);
    }
  });
}

test("all presentation cases match validity and expected first issue", async (context) => {
  await assertValidationCases(context, corpus.presentation_cases, validatePresentation);
});

test("all connector binding cases match validity and expected first issue", async (context) => {
  await assertValidationCases(context, corpus.connector_binding_cases, validateConnectorBinding);
});

test("all normalized product cases match validity and expected first issue", async (context) => {
  await assertValidationCases(context, corpus.normalized_product_cases, validateNormalizedProduct);
});

test("presentation rejects a non-rigid camera transform", () => {
  const valid = corpus.presentation_cases.find((item) => item.valid);
  assert.ok(valid !== undefined);
  const presentation = asRecord(parseStrictJson(decode(valid.payload_base64)));
  const camera = asRecords(presentation.cameras)[0];
  asRecord(camera.transform).x_axis = [2, 0, 0];
  const result = validatePresentation(presentation);
  assert.equal(result.firstError?.code, "transform_invalid");
  assert.equal(result.firstError?.path, "/cameras/0/transform");
});

function artifactBlobs(): Map<string, Buffer> {
  const result = new Map<string, Buffer>();
  for (const artifact of Object.values(corpus.artifacts)) {
    if (artifact.uri !== undefined) result.set(artifact.uri, decode(artifact.base64));
  }
  return result;
}

type JsonRecord = Record<string, unknown>;

function asRecord(value: unknown): JsonRecord {
  assert.ok(value !== null && typeof value === "object" && !Array.isArray(value));
  return value as JsonRecord;
}

function asRecords(value: unknown): JsonRecord[] {
  assert.ok(Array.isArray(value));
  return value.map(asRecord);
}

function validScene(): JsonRecord {
  return asRecord(parseStrictJson(decode(corpus.artifacts.scene.base64)));
}

function validEntities(): JsonRecord {
  return asRecord(parseStrictJson(decode(corpus.artifacts.entities.base64)));
}

function operationSource(path: string, callText: string): JsonRecord {
  const source: JsonRecord = {
    schema_version: "1.0",
    path,
    path_kind: "project_relative",
    line: 1,
    column: 7,
    end_line: 1,
    end_column: 7 + Array.from(callText).length,
    call_text: callText,
    callsite_id: "",
    assignment_targets: ["body"],
  };
  const material = [
    source.path,
    source.line,
    source.column,
    source.end_line,
    source.end_column,
    source.call_text,
  ].map(String).join("\x1f");
  source.callsite_id = `callsite_${sha256(Buffer.from(material, "utf8")).slice("sha256:".length, "sha256:".length + 16)}`;
  return source;
}

function embeddedSourcePackage(): {
  blobs: Map<string, Buffer>;
  manifest: JsonRecord;
  model: JsonRecord;
  sourcePath: string;
  sourceUri: string;
} {
  const scene = validScene();
  const sidecar = validEntities();
  makeModelScene(scene, sidecar, "shape");

  const definition = asRecords(scene.definitions)[0];
  const definitionId = "definition/root/shape/model/graph/node/0";
  definition.definition_id = definitionId;
  asRecords(scene.nodes)[0].definition_id = definitionId;
  sidecar.definition_id = definitionId;

  const callText = "scad.make_box_rsolid(width=1)";
  const sourcePath = "models/box.py";
  const sourceUri = `sources/${sourcePath}`;
  const sourceBytes = Buffer.from(`body = ${callText}\n`, "utf8");
  const model: JsonRecord = {
    schema_version: "2.0",
    graph: {
      graph_id: "graph",
      nodes: [{
        node_id: "node",
        op: "make_box_rsolid",
        params: { width: 1 },
        inputs: [],
        output_count: 1,
        source: operationSource(sourcePath, callText),
      }],
    },
    leaf_ids: ["node"],
  };
  const modelBytes = canonicalJsonBytes(model);
  scene.source = {
    kind: "model",
    graph_id: "graph",
    model_schema_version: "2.0",
    artifact_hash: sha256(modelBytes),
    embedded_artifact_uri: "model/model.json",
    embedded_artifact_byte_length: modelBytes.length,
    source_files: [{
      path: sourcePath,
      uri: sourceUri,
      media_type: "text/x-python; charset=utf-8",
      byte_length: sourceBytes.length,
      content_hash: sha256(sourceBytes),
    }],
  };
  asRecord(scene.compile_options).embed_source = true;
  const replaced = replaceEntitySidecar(scene, sidecar);
  replaced.blobs.set("model/model.json", modelBytes);
  replaced.blobs.set(sourceUri, sourceBytes);
  scene.revision = computeSceneRevision(scene);
  return { blobs: replaced.blobs, manifest: scene, model, sourcePath, sourceUri };
}

function replaceEmbeddedModel(
  fixture: ReturnType<typeof embeddedSourcePackage>,
): void {
  const payload = canonicalJsonBytes(fixture.model);
  fixture.blobs.set("model/model.json", payload);
  const source = asRecord(fixture.manifest.source);
  source.artifact_hash = sha256(payload);
  source.embedded_artifact_byte_length = payload.length;
  fixture.manifest.revision = computeSceneRevision(fixture.manifest);
}

function replaceEntitySidecar(
  scene: JsonRecord,
  sidecar: JsonRecord,
): { manifest: Buffer; blobs: Map<string, Buffer>; entityUri: string } {
  const entityBytes = canonicalJsonBytes(sidecar);
  const entityHash = sha256(entityBytes);
  const entityUri = `entities/sha256-${entityHash.slice("sha256:".length)}.json`;
  const entityRecord = asRecords(scene.entity_assets)[0];
  const oldUri = entityRecord.uri as string;
  Object.assign(entityRecord, {
    byte_length: entityBytes.length,
    content_hash: entityHash,
    entity_asset_id: entityHash,
    uri: entityUri,
  });
  asRecords(scene.definitions)[0].entity_asset_id = entityHash;
  scene.revision = computeSceneRevision(scene);
  const blobs = artifactBlobs();
  blobs.delete(oldUri);
  blobs.set(entityUri, entityBytes);
  return { manifest: canonicalJsonBytes(scene), blobs, entityUri };
}

function entityIndex(sidecar: JsonRecord, kind: string): number {
  const index = asRecords(sidecar.entities).findIndex((entity) => entity.kind === kind);
  assert.notEqual(index, -1);
  return index;
}

function assertFirstIssue(
  result: ReturnType<typeof validateSceneManifest>,
  code: string,
  path: string,
): void {
  assert.equal(result.valid, false);
  assert.equal(result.firstError?.code, code);
  assert.equal(result.firstError?.path, path);
}

test("scene semantic references and content identities reject independent mutations", async (context) => {
  const missingHash = `sha256:${"f".repeat(64)}`;
  const cases: [string, (scene: JsonRecord) => void, string, string][] = [
    ["missing definition appearance", (scene) => {
      asRecords(scene.definitions)[0].appearance_id = `appearance/evaluated/${"f".repeat(64)}`;
    }, "reference_missing", "/definitions/0/appearance_id"],
    ["missing definition geometry asset", (scene) => {
      asRecords(scene.definitions)[0].geometry_asset_id = missingHash;
    }, "reference_missing", "/definitions"],
    ["missing node appearance override", (scene) => {
      asRecords(scene.nodes)[0].appearance_override_id = `appearance/evaluated/${"f".repeat(64)}`;
    }, "reference_missing", "/nodes/0/appearance_override_id"],
    ["geometry asset ID differs from content hash", (scene) => {
      asRecords(scene.geometry_assets)[0].content_hash = missingHash;
    }, "source_matrix_invalid", "/geometry_assets/0/asset_id"],
    ["entity asset ID differs from content hash", (scene) => {
      asRecords(scene.entity_assets)[0].content_hash = missingHash;
    }, "source_matrix_invalid", "/entity_assets/0/entity_asset_id"],
    ["entity asset URI is not content-derived", (scene) => {
      asRecords(scene.entity_assets)[0].uri = "entities/noncanonical.json";
    }, "source_matrix_invalid", "/entity_assets/0/uri"],
    ["geometry tessellation differs from compile options", (scene) => {
      asRecord(asRecords(scene.geometry_assets)[0].tessellation).linear_tolerance = 0.02;
    }, "source_matrix_invalid", "/geometry_assets/0/tessellation/linear_tolerance"],
    ["appearance ID is not content-derived", (scene) => {
      const appearanceId = `appearance/evaluated/${"f".repeat(64)}`;
      asRecords(scene.appearances)[0].appearance_id = appearanceId;
      asRecords(scene.definitions)[0].appearance_id = appearanceId;
    }, "source_matrix_invalid", "/appearances/0/appearance_id"],
    ["manual source cannot request embedding", (scene) => {
      asRecord(scene.compile_options).embed_source = true;
    }, "source_matrix_invalid", "/source"],
    ["definition ID must be source-derived", (scene) => {
      asRecord(scene.source).source_id = "other";
      asRecord(asRecords(scene.definitions)[0].source).source_id = "other";
    }, "source_matrix_invalid", "/definitions/0/definition_id"],
  ];
  for (const [name, mutate, code, path] of cases) await context.test(name, () => {
    const scene = validScene();
    mutate(scene);
    scene.revision = computeSceneRevision(scene);
    assertFirstIssue(validateSceneManifest(scene), code, path);
  });
});

function addSceneCamera(scene: JsonRecord): JsonRecord {
  const camera = {
    camera_id: "camera/test",
    name: "Test camera",
    projection: "perspective",
    parent_node_id: null,
    transform: structuredClone(asRecords(scene.nodes)[0].transform),
    near: 1,
    far: 10,
    vertical_fov_degrees: 45,
  };
  assert.ok(Array.isArray(scene.cameras));
  scene.cameras.push(camera);
  return camera;
}

test("scene cameras reject dangling parents and reversed clipping bounds independently", async (context) => {
  await context.test("dangling parent", () => {
    const scene = validScene();
    addSceneCamera(scene).parent_node_id = "instance/missing";
    scene.revision = computeSceneRevision(scene);
    assertFirstIssue(validateSceneManifest(scene), "reference_missing", "/cameras/0/parent_node_id");
  });
  await context.test("far does not exceed near", () => {
    const scene = validScene();
    addSceneCamera(scene).far = 1;
    scene.revision = computeSceneRevision(scene);
    assertFirstIssue(validateSceneManifest(scene), "bounds_invalid", "/cameras/0/far");
  });
});

test("entity kind, frame, status, position, and bounds semantics reject independent mutations", async (context) => {
  const cases: [string, string, (entity: JsonRecord) => void, string, (index: number) => string][] = [
    ["geometry kind", "solid", (entity) => {
      entity.geometry = { type: "point", position: [0, 0, 0] };
    }, "entity_topology_invalid", (index) => `/entities/${index}/geometry/type`],
    ["required connector frame", "face", (entity) => {
      entity.sdk_connector_frame = null;
    }, "connector_invalid", (index) => `/entities/${index}/sdk_connector_frame`],
    ["render status", "vertex", (entity) => {
      entity.render_status = "degenerate";
    }, "entity_topology_invalid", (index) => `/entities/${index}/render_status`],
    ["vertex property position", "vertex", (entity) => {
      const position = [...(asRecord(entity.properties).position as number[])];
      position[0] += 1;
      asRecord(entity.properties).position = position;
    }, "bounds_invalid", (index) => `/entities/${index}/properties/position`],
    ["reversed bounds", "solid", (entity) => {
      const bounds = asRecord(asRecord(entity.properties).bounds);
      const maximum = bounds.max as number[];
      const minimum = [...(bounds.min as number[])];
      minimum[0] = maximum[0] + 1;
      bounds.min = minimum;
    }, "bounds_invalid", (index) => `/entities/${index}/properties/bounds`],
  ];
  for (const [name, kind, mutate, code, path] of cases) await context.test(name, () => {
    const sidecar = validEntities();
    const index = entityIndex(sidecar, kind);
    mutate(asRecords(sidecar.entities)[index]);
    assertFirstIssue(validateEntityAsset(sidecar), code, path(index));
  });
});

test("analytic geometry coordinates enforce the scene coordinate limit", async (context) => {
  const cases: [string, string, (geometry: JsonRecord) => void][] = [
    ["point.position", "vertex", (geometry) => { geometry.position = [1e12 + 1, 0, 0]; }],
    ["line.origin", "edge", (geometry) => { geometry.origin = [0, -(1e12 + 1), 0]; }],
    ["plane.origin", "face", (geometry) => { geometry.origin = [0, 0, 1e12 + 1]; }],
    ["circle.center", "edge", (geometry) => {
      for (const key of Object.keys(geometry)) delete geometry[key];
      Object.assign(geometry, {
        type: "circle",
        center: [1e12 + 1, 0, 0],
        normal: [0, 0, 1],
        x_direction: [1, 0, 0],
        radius: 1,
      });
    }],
  ];
  for (const [name, kind, mutate] of cases) await context.test(name, () => {
    const sidecar = validEntities();
    const index = entityIndex(sidecar, kind);
    const geometry = asRecord(asRecords(sidecar.entities)[index].geometry);
    mutate(geometry);
    const result = validateEntityAsset(sidecar);
    assert.equal(result.valid, false);
    assert.ok(result.issues.some((item) =>
      item.code === "analytic_geometry_invalid" &&
      item.path === `/entities/${index}/geometry/${name.split(".")[1]}`
    ));
  });
});

test("package checks entity geometry engine version against the manifest", () => {
  const scene = validScene();
  const sidecar = validEntities();
  asRecord(sidecar.geometry_engine).version = "different";
  const { manifest, blobs } = replaceEntitySidecar(scene, sidecar);
  const result = validateScenePackage(manifest, blobs);
  assert.ok(result.issues.some((item) =>
    item.code === "source_matrix_invalid" && item.path === "/definitions/0/entity_asset_id"
  ));
});

test("package rejects entity source variants incompatible with the scene source", () => {
  const scene = validScene();
  const sidecar = validEntities();
  asRecords(sidecar.entities)[0].source = {
    kind: "imported_primitive",
    source_element_id: "element",
  };
  const { manifest, blobs, entityUri } = replaceEntitySidecar(scene, sidecar);
  const result = validateScenePackage(manifest, blobs);
  assert.ok(result.issues.some((item) =>
    item.code === "source_matrix_invalid" && item.path === `/${entityUri}/entities/0/source`
  ));
});

function makeModelScene(scene: JsonRecord, sidecar: JsonRecord, definitionKind: "shape" | "part"): void {
  scene.source = {
    kind: "model",
    graph_id: "graph",
    model_schema_version: "2.0",
    artifact_hash: `sha256:${"1".repeat(64)}`,
  };
  const definition = asRecords(scene.definitions)[0];
  definition.kind = definitionKind;
  definition.source = definitionKind === "part"
    ? {
        kind: "product_model",
        root_id: "root",
        semantic_type: "Part",
        semantic_id: "Part",
        graph_id: "graph",
        node_id: "node",
        output_slot: 0,
      }
    : {
        kind: "model_output",
        root_id: "root",
        graph_id: "graph",
        node_id: "node",
        output_slot: 0,
      };
  for (const entity of asRecords(sidecar.entities)) {
    entity.source = {
      kind: "model_output",
      graph_id: "graph",
      node_id: "node",
      output_slot: 0,
    };
  }
}

test("package checks model entity source ownership fields", () => {
  const scene = validScene();
  const sidecar = validEntities();
  makeModelScene(scene, sidecar, "shape");
  asRecord(asRecords(sidecar.entities)[0].source).node_id = "other-node";
  const { manifest, blobs, entityUri } = replaceEntitySidecar(scene, sidecar);
  const result = validateScenePackage(manifest, blobs);
  assert.ok(result.issues.some((item) =>
    item.code === "source_matrix_invalid" && item.path === `/${entityUri}/entities/0/source`
  ));
});

test("embedded model and Python source package validates", () => {
  const fixture = embeddedSourcePackage();
  const result = validateScenePackage(fixture.manifest, fixture.blobs);
  assert.equal(result.valid, true, JSON.stringify(result.issues));
});

test("manifest rejects archive-unsafe embedded Python paths", () => {
  const fixture = embeddedSourcePackage();
  const sourceFile = asRecords(asRecord(fixture.manifest.source).source_files)[0];
  sourceFile.path = "models/../box.py";
  sourceFile.uri = "sources/models/../box.py";
  fixture.manifest.revision = computeSceneRevision(fixture.manifest);

  const result = validateSceneManifest(fixture.manifest);
  assert.ok(result.issues.some((item) =>
    item.code === "source_matrix_invalid" && item.path === "/source/source_files/0/path"
  ));
});

test("package rejects malformed operation source mappings", () => {
  const fixture = embeddedSourcePackage();
  const graph = asRecord(fixture.model.graph);
  const source = asRecord(asRecords(graph.nodes)[0].source);
  delete source.callsite_id;
  replaceEmbeddedModel(fixture);

  const result = validateScenePackage(fixture.manifest, fixture.blobs);
  assert.ok(result.issues.some((item) =>
    item.code === "source_matrix_invalid" && item.path === "/model/model.json/graph/nodes/0/source"
  ));
});

test("package rejects invalid UTF-8 Python source bytes", () => {
  const fixture = embeddedSourcePackage();
  const payload = Buffer.from([0xff]);
  fixture.blobs.set(fixture.sourceUri, payload);
  const sourceFile = asRecords(asRecord(fixture.manifest.source).source_files)[0];
  sourceFile.byte_length = payload.length;
  sourceFile.content_hash = sha256(payload);
  fixture.manifest.revision = computeSceneRevision(fixture.manifest);

  const result = validateScenePackage(fixture.manifest, fixture.blobs);
  assert.ok(result.issues.some((item) =>
    item.code === "invalid_utf8" && item.path === `/${fixture.sourceUri}`
  ));
});

test("package binding status rules follow Python precedence", async (context) => {
  await context.test("solid is always not_applicable", () => {
    const scene = validScene();
    const sidecar = validEntities();
    const index = entityIndex(sidecar, "solid");
    asRecords(sidecar.entities)[index].connector_binding_status = "supported";
    const { manifest, blobs, entityUri } = replaceEntitySidecar(scene, sidecar);
    const result = validateScenePackage(manifest, blobs);
    const found = result.issues.find((item) => item.code === "connector_invalid" && item.path === `/${entityUri}/entities/${index}/connector_binding_status`);
    assert.match(found?.message ?? "", /not_applicable/);
  });

  await context.test("non-part owner precedes scene source", () => {
    const scene = validScene();
    const sidecar = validEntities();
    const index = entityIndex(sidecar, "face");
    asRecords(sidecar.entities)[index].connector_binding_status = "source_not_model";
    const { manifest, blobs, entityUri } = replaceEntitySidecar(scene, sidecar);
    const result = validateScenePackage(manifest, blobs);
    const found = result.issues.find((item) => item.code === "connector_invalid" && item.path === `/${entityUri}/entities/${index}/connector_binding_status`);
    assert.match(found?.message ?? "", /owner_not_part/);
  });

  await context.test("non-model part requires source_not_model", () => {
    const scene = validScene();
    const sidecar = validEntities();
    const definition = asRecords(scene.definitions)[0];
    definition.kind = "part";
    definition.source = {
      kind: "product_manual",
      root_id: "root",
      semantic_type: "Part",
      semantic_id: "Part",
    };
    const entities = asRecords(sidecar.entities);
    for (const entity of entities) {
      if (entity.kind !== "solid") entity.connector_binding_status = "source_not_model";
    }
    const index = entityIndex(sidecar, "face");
    entities[index].connector_binding_status = "supported";
    const { manifest, blobs, entityUri } = replaceEntitySidecar(scene, sidecar);
    const result = validateScenePackage(manifest, blobs);
    const found = result.issues.find((item) => item.code === "connector_invalid" && item.path === `/${entityUri}/entities/${index}/connector_binding_status`);
    assert.match(found?.message ?? "", /source_not_model/);
  });

  await context.test("model part null frame requires frame_undefined", () => {
    const scene = validScene();
    const sidecar = validEntities();
    makeModelScene(scene, sidecar, "part");
    const entities = asRecords(sidecar.entities);
    for (const entity of entities) {
      if (entity.kind !== "solid") entity.connector_binding_status = "supported";
    }
    const index = entityIndex(sidecar, "edge");
    entities[index].sdk_connector_frame = null;
    entities[index].connector_binding_status = "owner_not_part";
    const { manifest, blobs, entityUri } = replaceEntitySidecar(scene, sidecar);
    const result = validateScenePackage(manifest, blobs);
    const found = result.issues.find((item) => item.code === "connector_invalid" && item.path === `/${entityUri}/entities/${index}/connector_binding_status`);
    assert.match(found?.message ?? "", /frame_undefined/);
  });
});

test("all package cases match validity and expected first issue", async (context) => {
  for (const item of corpus.package_cases) await context.test(item.name, () => {
    const result = validateScenePackage(
      decode(item.manifest_base64),
      corpusBlobs(corpus.blobs, item),
    );
    assert.equal(result.valid, item.valid);
    if (item.expected !== null) {
      assert.equal(result.firstError?.code, item.expected.code);
      assert.equal(result.firstError?.path, item.expected.path);
  }
});

test("accepted package fixtures cover every connector binding status", () => {
  const statuses = new Set<string>();
  for (const item of [...corpus.package_cases, ...corpus.scene_shape_cases]) {
    if (!item.valid) continue;
    for (const [uri, payload] of corpusBlobs(corpus.blobs, item)) {
      if (!uri.startsWith("entities/")) continue;
      const sidecar = asRecord(parseCanonicalJson(payload));
      for (const entity of asRecords(sidecar.entities)) {
        statuses.add(String(entity.connector_binding_status));
      }
    }
  }
  assert.deepEqual([...statuses].sort(), [
    "frame_undefined",
    "not_applicable",
    "owner_not_part",
    "selector_ambiguous",
    "selector_unstable",
    "source_not_model",
    "supported",
  ]);
});
});

test("scene field matrix replays independently", async (context) => {
  const scene = validScene();
  for (const item of corpus.scene_field_cases) await context.test(item.name, () => {
    const result = validateSceneManifest(
      canonicalJsonBytes(applySceneFieldCase(scene, item)),
    );
    assert.equal(result.valid, item.valid);
    assert.equal(result.firstError?.code, item.expected?.code);
    assert.equal(result.firstError?.path, item.expected?.path);
  });
});

test("scene shapes validate, round trip, and characterize asset reuse", async (context) => {
  for (const item of corpus.scene_shape_cases) await context.test(item.name, () => {
    const manifest = decode(item.manifest_base64);
    const scene = asRecord(parseCanonicalJson(manifest));
    const result = validateScenePackage(manifest, corpusBlobs(corpus.blobs, item));
    assert.equal(result.valid, item.valid);
    assert.equal(result.firstError?.code, item.expected?.code);
    assert.equal(result.firstError?.path, item.expected?.path);
    assert.deepEqual(canonicalJsonBytes(scene), manifest);
    assert.deepEqual(
      canonicalJsonBytes(sceneShapeFacts(scene)),
      canonicalJsonBytes(item.expected_shape),
    );

    const definitions = new Map(
      asRecords(scene.definitions).map((definition) => [
        String(definition.definition_id),
        definition,
      ]),
    );
    for (const [definitionId, count] of Object.entries(
      item.expected_shape.definition_occurrence_counts,
    )) {
      if (count <= 1) continue;
      const occurrences = asRecords(scene.nodes).filter(
        (node) => node.definition_id === definitionId,
      );
      assert.equal(occurrences.length, count);
      assert.equal(new Set(occurrences.map((node) => node.definition_id)).size, 1);
      assert.notEqual(definitions.get(definitionId)?.geometry_asset_id, null);
    }
  });
});

test("two-pass revision vectors reproduce exact drafts, revisions, and bytes", async (context) => {
  for (const vector of corpus.revision_vectors) await context.test(vector.name, () => {
    const draftBytes = decode(vector.draft_base64);
    const draft = asRecord(parseCanonicalJson(draftBytes));
    const sceneBytes = decode(vector.canonical_base64);
    const scene = withSceneRevision(draft);
    assert.deepEqual(canonicalJsonBytes(draft), draftBytes);
    assert.equal(scene.revision, vector.revision);
    assert.deepEqual(canonicalJsonBytes(scene), sceneBytes);
    assert.equal(sha256(sceneBytes), vector.sha256);
  });
});

test("all GLB cases match acceptance, kind, and exact rejection", async (context) => {
  for (const item of corpus.glb_cases) await context.test(item.name, () => {
    if (item.valid) {
      const result = preflightGlb(decode(item.payload_base64), item.expected_kind);
      assert.equal(result.kind, item.kind);
    } else {
      assert.throws(() => preflightGlb(decode(item.payload_base64), item.expected_kind), (error) => {
        assert.equal((error as Error).message, item.error);
        return true;
      });
    }
  });
});

test("all ZIP cases match acceptance, deflate use, and exact rejection", async (context) => {
  for (const item of corpus.zip_cases) await context.test(item.name, () => {
    if (item.valid) {
      const result = preflightZipBytes(decode(item.payload_base64));
      assert.equal(result.usedDeflate, item.used_deflate);
    } else {
      assert.throws(() => preflightZipBytes(decode(item.payload_base64)), (error) => {
        assert.equal((error as Error).message, item.error);
        return true;
      });
    }
  });
});

function f64FromHex(value: string): number {
  return Buffer.from(value, "hex").readDoubleBE(0);
}

function f64Hex(value: number): string {
  const bytes = Buffer.allocUnsafe(8);
  bytes.writeDoubleBE(value, 0);
  return bytes.toString("hex");
}

test("numeric profile vectors reproduce exact IEEE-754 results", async (context) => {
  for (const vector of corpus.numeric_vectors) await context.test(vector.name, () => {
    try {
      let actual: string | string[];
      if (vector.operation === "f32") {
        const input = vector.input_bits as string[];
        actual = profileF32Bits(f64FromHex(input[0])).toString(16).padStart(8, "0");
      } else if (vector.operation === "cross") {
        const [left, right] = (vector.input_bits as string[][]).map(
          (input) => input.map(f64FromHex) as [number, number, number],
        );
        actual = profileCross(left, right).map(f64Hex);
      } else {
        const input = (vector.input_bits as string[][])[0].map(f64FromHex) as [number, number, number];
        actual = profileNormalize(input).map((component) =>
          profileF32Bits(component).toString(16).padStart(8, "0")
        );
      }
      assert.equal(vector.valid, true);
      assert.deepEqual(actual, vector.expected_bits);
    } catch (error) {
      assert.equal(vector.valid, false);
      assert.equal((error as Error).message, vector.error);
    }
  });
});

test("resource profile and exact boundary cases match Python", async (context) => {
  assert.deepEqual(BASE_LIMITS, Object.fromEntries(Object.entries(corpus.resource_limits)));
  const scene = validScene();

  for (const item of corpus.resource_cases) await context.test(item.name, () => {
    let valid = false;
    let error: string | null = null;
    let first: ExpectedIssue | null = null;
    try {
      const parameters = item.parameters;
      const limits = { ...BASE_LIMITS, ...(parameters.limits as Partial<SceneResourceLimits> ?? {}) };
      if (item.operation === "input_archive_size") {
        preflightInputArchiveSize(parameters.size as number, limits);
        valid = true;
      } else if (item.operation === "archive_member_sizes" || item.operation === "archive_member_count") {
        let sizes: Map<string, number>;
        if (item.operation === "archive_member_sizes") {
          sizes = new Map(Object.entries(parameters.sizes as Record<string, number>));
        } else {
          sizes = new Map([["scene.json", 0]]);
          for (let index = 0; index < (parameters.count as number) - 1; index += 1) {
            sizes.set(`x/${index.toString().padStart(5, "0")}`, 0);
          }
        }
        preflightArchiveMemberSizes(sizes, limits);
        valid = true;
      } else if (item.operation === "aggregate_compression_ratio" || item.operation === "member_compression_ratio") {
        const callback = item.operation === "aggregate_compression_ratio"
          ? preflightAggregateCompressionRatio
          : preflightMemberCompressionRatio;
        callback(parameters.uncompressed_size as number, parameters.compressed_size as number, limits);
        valid = true;
      } else if (item.operation === "json_depth") {
        const value: JsonRecord = {};
        let current = value;
        for (let index = 0; index < (parameters.depth as number); index += 1) {
          current.x = {};
          current = asRecord(current.x);
        }
        const result = report(jsonResourceIssues(value, limits));
        valid = result.valid;
        first = result.firstError === null ? null : { code: result.firstError.code, path: result.firstError.path };
      } else if (item.operation === "json_domain") {
        const text = parameters.text as string;
        const kind = parameters.kind as string;
        const field = parameters.field as string | null;
        let value: JsonRecord;
        if (kind === "value") value = { value: text };
        else if (kind === "object_key") value = { [text]: 0 };
        else if (kind === "metadata_key") value = { metadata: { [text]: 0 } };
        else if (kind === "sdk_metadata_key") value = { sdk_metadata: { [text]: 0 } };
        else if (kind === "identifier") value = { [field ?? "node_id"]: text };
        else if (kind === "identifier_array") value = { [field ?? "component_path"]: [text] };
        else if (kind === "uri") value = { uri: text };
        else throw new Error(`unknown JSON domain kind: ${kind}`);
        const result = report(jsonResourceIssues(value, limits));
        valid = result.valid;
        first = result.firstError === null ? null : { code: result.firstError.code, path: result.firstError.path };
      } else if (item.operation === "resource_count") {
        const count = parameters.count as number;
        const kind = parameters.kind as string;
        const field = parameters.field as string | null;
        let value: JsonRecord;
        if (kind === "collection") value = { [field!]: Array(count).fill(null) };
        else if (kind === "hierarchy") value = { nodes: [{ source: { component_path: Array(count).fill("x") } }] };
        else if (kind === "forwarded") {
          value = {
            connectors: Array.from({ length: count }, (_unused, index) => ({
              anchor_kind: "forwarded",
              connector_snapshot_id: `c${index}`,
              forwarded_from: { source_connector_snapshot_id: `c${index + 1}` },
            })),
          };
        } else throw new Error(`unknown resource count kind: ${kind}`);
        const result = report(resourceCountIssues(value, parameters.artifact as "scene" | "entities" | "presentation", limits));
        valid = result.valid;
        first = result.firstError === null ? null : { code: result.firstError.code, path: result.firstError.path };
      } else if (item.operation === "glb_counts") {
        preflightGlbCounts(
          parameters.kind as "triangle" | "line",
          parameters.vertex_count as number,
          parameters.index_count as number,
          limits,
        );
        valid = true;
      } else if (item.operation === "package_budget") {
        const input = parameters.contributions as {
          scene_json_bytes: number;
          glb_decoded_buffer_bytes: number;
          entity_json_bytes: number;
          other_immutable_json_bytes: number;
          entity_count: number;
          entity_vertex_count: number;
          triangle_vertex_count: number;
          triangle_count: number;
          line_vertex_count: number;
          line_segment_count: number;
        };
        const totals = computePackageBudgetTotals({
          sceneJsonBytes: input.scene_json_bytes,
          glbDecodedBufferBytes: input.glb_decoded_buffer_bytes,
          entityJsonBytes: input.entity_json_bytes,
          otherImmutableJsonBytes: input.other_immutable_json_bytes,
          entityCount: input.entity_count,
          entityVertexCount: input.entity_vertex_count,
          triangleVertexCount: input.triangle_vertex_count,
          triangleCount: input.triangle_count,
          lineVertexCount: input.line_vertex_count,
          lineSegmentCount: input.line_segment_count,
        });
        const result = report(packageBudgetIssues(totals, limits), "package");
        valid = result.valid;
        first = result.firstError === null ? null : { code: result.firstError.code, path: result.firstError.path };
      } else if (item.operation === "scene_geometry_byte_length") {
        let value = structuredClone(scene);
        const byteLength = Number(parameters.value);
        asRecords(value.geometry_assets)[0].byte_length = byteLength;
        if (byteLength <= Number.MAX_SAFE_INTEGER) value = withSceneRevision(value);
        const result = validateSceneManifest(value);
        valid = result.valid;
        first = result.firstError === null ? null : { code: result.firstError.code, path: result.firstError.path };
      } else if (item.operation === "scene_compile_option") {
        const value = structuredClone(scene);
        const field = parameters.field as string;
        const number = parameters.value as number;
        asRecord(value.compile_options)[field] = number;
        asRecord(asRecords(value.geometry_assets)[0].tessellation)[field] = number;
        if (field === "linear_tolerance") asRecord(asRecords(value.edge_assets)[0].tessellation)[field] = number;
        const result = validateSceneManifest(withSceneRevision(value));
        valid = result.valid;
        first = result.firstError === null ? null : { code: result.firstError.code, path: result.firstError.path };
      } else {
        throw new Error(`unknown resource operation: ${item.operation}`);
      }
    } catch (caught) {
      valid = false;
      error = (caught as Error).message;
    }
    assert.equal(valid, item.valid);
    if (Object.hasOwn(item, "error")) assert.equal(error, item.error ?? null);
    if (item.expected !== undefined && item.expected !== null) {
      assert.equal(first?.code, item.expected.code);
      assert.equal(first?.path, item.expected.path);
    }
  });
});

test("canonical stored ZIP reproduces the exact shared vector", () => {
  const expected = decode(corpus.artifacts.canonical_zip.base64);
  const archive = preflightZipBytes(expected);
  assert.equal(archive.inputSize, archive.canonicalSize);
  assert.deepEqual(canonicalZipBytes(archive.members), expected);
  assert.equal(`sha256:${createHash("sha256").update(expected).digest("hex")}`, corpus.artifacts.canonical_zip.sha256);
});
