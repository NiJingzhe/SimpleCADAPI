import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  canonicalJsonBytes,
  computeSceneRevision,
  parseStrictJson,
  sha256,
} from "../src/canonical.js";
import { report } from "../src/report.js";
import {
  computePackageBudgetTotals,
  packageBudgetIssues,
  validateSceneManifest,
  validateScenePackage,
} from "../src/validation.js";

type JsonRecord = Record<string, unknown>;

interface Artifact {
  base64: string;
  uri?: string;
}

interface Corpus {
  artifacts: Record<string, Artifact>;
  presentation_cases: { valid: boolean; payload_base64: string }[];
}

const here = dirname(fileURLToPath(import.meta.url));
const corpusPath = resolve(here, "../../../test/fixtures/scene-contract/corpus.json");
const corpus = parseStrictJson(readFileSync(corpusPath)) as Corpus;
const decode = (value: string): Buffer => Buffer.from(value, "base64");

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

function artifactBlobs(): Map<string, Buffer> {
  const result = new Map<string, Buffer>();
  for (const artifact of Object.values(corpus.artifacts)) {
    if (artifact.uri !== undefined) result.set(artifact.uri, decode(artifact.base64));
  }
  return result;
}

function validPresentation(): JsonRecord {
  const value = corpus.presentation_cases.find((item) => item.valid);
  assert.ok(value !== undefined);
  return asRecord(parseStrictJson(decode(value.payload_base64)));
}

function utf8Compare(left: string, right: string): number {
  return Buffer.compare(Buffer.from(left, "utf8"), Buffer.from(right, "utf8"));
}

function attachPresentation(scene: JsonRecord, blobs: Map<string, Buffer>): { presentation: JsonRecord; blobs: Map<string, Buffer> } {
  const presentation = validPresentation();
  const presentationId = presentation.presentation_id as string;
  const expectedAppearanceIds = new Map<unknown, string>();
  const sceneAppearances = asRecords(scene.appearances);
  for (const authored of asRecords(presentation.appearances)) {
    const evaluated: JsonRecord = {
      alpha_mode: authored.alpha_mode,
      base_color: authored.base_color,
      double_sided: authored.double_sided,
      edge_color: authored.edge_color,
      metallic: authored.metallic,
      name: authored.name,
      roughness: authored.roughness,
      sdk_metadata: {},
      source: {
        appearance_name: authored.name,
        kind: "presentation",
        presentation_id: presentationId,
      },
    };
    const appearanceId = `appearance/evaluated/${sha256(canonicalJsonBytes(evaluated)).slice("sha256:".length)}`;
    expectedAppearanceIds.set(authored.name, appearanceId);
    sceneAppearances.push({ appearance_id: appearanceId, ...evaluated });
  }
  sceneAppearances.sort((left, right) => utf8Compare(left.appearance_id as string, right.appearance_id as string));
  scene.appearances = sceneAppearances;

  const nodeMap = new Map(asRecords(scene.nodes).map((node) => [node.node_id, node]));
  for (const override of asRecords(presentation.node_overrides)) {
    const node = nodeMap.get(override.node_id);
    assert.ok(node !== undefined);
    if (override.visible !== undefined) node.visible = override.visible;
    if (override.appearance_name !== undefined) node.appearance_override_id = expectedAppearanceIds.get(override.appearance_name);
  }
  scene.cameras = asRecords(presentation.cameras).map((camera) => ({
    camera_id: `camera/${presentationId}/${String(camera.name)}`,
    ...camera,
  }));

  const presentationBytes = canonicalJsonBytes(presentation);
  asRecord(scene.compile_options).embed_presentation = true;
  scene.presentation_source = {
    artifact_hash: sha256(presentationBytes),
    embedded_artifact_byte_length: presentationBytes.length,
    embedded_artifact_uri: "presentation/presentation.json",
    presentation_id: presentationId,
    schema_version: "1.0",
  };
  scene.revision = computeSceneRevision(scene);
  const resultBlobs = new Map(blobs);
  resultBlobs.set("presentation/presentation.json", presentationBytes);
  return { presentation, blobs: resultBlobs };
}

function replacePresentation(scene: JsonRecord, blobs: Map<string, Buffer>, payload: Buffer): Map<string, Buffer> {
  const source = asRecord(scene.presentation_source);
  source.artifact_hash = sha256(payload);
  source.embedded_artifact_byte_length = payload.length;
  scene.revision = computeSceneRevision(scene);
  const result = new Map(blobs);
  result.set("presentation/presentation.json", payload);
  return result;
}

test("package budget formula and first error match Python with declarative limits", () => {
  const totals = computePackageBudgetTotals({
    sceneJsonBytes: 7,
    glbDecodedBufferBytes: 11,
    entityJsonBytes: 13,
    otherImmutableJsonBytes: 17,
    entityCount: 23,
    entityVertexCount: 19,
    triangleVertexCount: 29,
    triangleCount: 31,
    lineVertexCount: 37,
    lineSegmentCount: 41,
  });
  assert.deepEqual(totals, {
    staticDecodedBufferBytes: 656,
    entityCount: 23,
    triangleVertexTotal: 29,
    triangleTotal: 31,
    lineVertexTotal: 37,
    lineSegmentTotal: 41,
  });
  assert.deepEqual(packageBudgetIssues(totals, {
    static_decoded_buffer_bytes: 656,
    entities_total: 23,
    triangle_vertices_total: 29,
    triangles_total: 31,
    line_vertices_total: 37,
    line_segments_total: 41,
  }), []);

  const result = report(packageBudgetIssues(totals, {
    static_decoded_buffer_bytes: 655,
    entities_total: 22,
    triangle_vertices_total: 28,
    triangles_total: 30,
    line_vertices_total: 36,
    line_segments_total: 40,
  }), "package");
  assert.deepEqual(
    result.firstError === null
      ? null
      : [result.firstError.code, result.firstError.path, result.firstError.message],
    ["resource_limit_exceeded", "", "total line GLB vertex count exceeds resource limit"],
  );
});

test("embedded presentation must be canonical and resolve exactly against the scene", () => {
  const scene = validScene();
  const attached = attachPresentation(scene, artifactBlobs());
  const validResult = validateScenePackage(canonicalJsonBytes(scene), attached.blobs);
  assert.equal(validResult.valid, true, JSON.stringify(validResult.issues));

  const noncanonical = Buffer.from(JSON.stringify(attached.presentation, null, 2));
  const blobs = replacePresentation(scene, attached.blobs, noncanonical);
  const result = validateScenePackage(canonicalJsonBytes(scene), blobs);
  assert.deepEqual(
    result.firstError === null ? null : [result.firstError.code, result.firstError.path],
    ["noncanonical_json", ""],
  );
});

test("embedded presentation IDs and scene references are contextual", async (context) => {
  const cases: [string, (presentation: JsonRecord) => void, string, string][] = [
    ["presentation ID", (presentation) => { presentation.presentation_id = "other"; }, "source_matrix_invalid", "/presentation/presentation.json/presentation_id"],
    ["source scene ID", (presentation) => { presentation.source_scene_id = "other"; }, "source_matrix_invalid", "/presentation/presentation.json/source_scene_id"],
    ["node override", (presentation) => { asRecords(presentation.node_overrides)[0].node_id = "instance/missing"; }, "source_matrix_invalid", "/presentation/presentation.json/node_overrides/0/node_id"],
    ["camera parent", (presentation) => { asRecords(presentation.cameras)[0].parent_node_id = "instance/missing"; }, "source_matrix_invalid", "/presentation/presentation.json/cameras/0/parent_node_id"],
  ];
  for (const [name, mutate, code, path] of cases) await context.test(name, () => {
    const scene = validScene();
    const attached = attachPresentation(scene, artifactBlobs());
    mutate(attached.presentation);
    const blobs = replacePresentation(scene, attached.blobs, canonicalJsonBytes(attached.presentation));
    const result = validateScenePackage(canonicalJsonBytes(scene), blobs);
    assert.ok(result.issues.some((item) => item.code === code && item.path === path));
  });
});

test("presentation appearance provenance and camera resolution are exact", () => {
  const scene = validScene();
  const attached = attachPresentation(scene, artifactBlobs());
  const sceneAppearances = asRecords(scene.appearances);
  const appearance = sceneAppearances.find((item) => item.source !== null && asRecord(item.source).kind === "presentation");
  assert.ok(appearance !== undefined);
  asRecord(appearance.source).appearance_name = "Other";
  const draft = { ...appearance };
  delete draft.appearance_id;
  const appearanceId = `appearance/evaluated/${sha256(canonicalJsonBytes(draft)).slice("sha256:".length)}`;
  appearance.appearance_id = appearanceId;
  asRecords(scene.nodes)[0].appearance_override_id = appearanceId;
  sceneAppearances.sort((left, right) => utf8Compare(left.appearance_id as string, right.appearance_id as string));
  scene.appearances = sceneAppearances;
  scene.cameras = [];
  scene.revision = computeSceneRevision(scene);

  const result = validateScenePackage(canonicalJsonBytes(scene), attached.blobs);
  const appearanceIndex = asRecords(scene.appearances).indexOf(appearance);
  assert.ok(result.issues.some((item) => item.code === "source_matrix_invalid" && item.path === `/appearances/${appearanceIndex}/source/appearance_name`));
  assert.ok(result.issues.some((item) => item.code === "source_matrix_invalid" && item.path === "/presentation/presentation.json/cameras/0"));
});

test("product material provenance must match a Part definition root", () => {
  const scene = validScene();
  const appearance = asRecords(scene.appearances)[0];
  appearance.source = { kind: "product_material", material_id: "steel", root_id: "other" };
  const draft = { ...appearance };
  delete draft.appearance_id;
  const appearanceId = `appearance/evaluated/${sha256(canonicalJsonBytes(draft)).slice("sha256:".length)}`;
  appearance.appearance_id = appearanceId;
  asRecords(scene.definitions)[0].appearance_id = appearanceId;
  scene.revision = computeSceneRevision(scene);

  const result = validateSceneManifest(scene);
  assert.ok(result.issues.some((item) => item.code === "source_matrix_invalid" && item.path === "/appearances/0/source/root_id"));
});

test("one URI cannot declare contradictory hash, length, or media roles", () => {
  const scene = validScene();
  const edge = asRecords(scene.edge_assets)[0];
  const oldUri = edge.uri as string;
  edge.uri = asRecords(scene.geometry_assets)[0].uri;
  scene.revision = computeSceneRevision(scene);
  const blobs = artifactBlobs();
  blobs.delete(oldUri);

  const result = validateScenePackage(canonicalJsonBytes(scene), blobs);
  assert.ok(result.issues.some((item) => item.code === "package_member_set_invalid"));
  assert.ok(result.issues.some((item) => item.code === "source_matrix_invalid" && item.path === "/edge_assets/0/uri"));
});
