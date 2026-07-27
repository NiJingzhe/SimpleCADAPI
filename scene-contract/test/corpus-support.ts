import assert from "node:assert/strict";
import { withSceneRevision } from "../src/index.js";

export interface ExpectedIssue { code: string; path: string }
export interface Mutation {
  operation: "add" | "delete" | "set";
  path: (string | number)[];
  value?: unknown;
}
export interface SceneFieldCase {
  name: string;
  valid: boolean;
  expected: ExpectedIssue | null;
  mutations: Mutation[];
  recompute_revision: boolean;
}
export interface PackageCase {
  name: string;
  valid: boolean;
  expected: ExpectedIssue | null;
  manifest_base64: string;
  blob_uris: string[];
  blob_mutations?: Record<string, string>;
}
export interface SceneShapeCase extends PackageCase {
  expected_shape: SceneShapeFacts;
}
export interface SceneShapeFacts {
  definition_count: number;
  definition_occurrence_counts: Record<string, number>;
  edge_asset_count: number;
  entity_asset_count: number;
  geometry_asset_count: number;
  maximum_depth: number;
  node_count: number;
  root_node_ids: string[];
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

export function corpusBlobs(
  pool: Record<string, string>,
  item: PackageCase,
): Map<string, Uint8Array> {
  const blobs = new Map<string, Uint8Array>(
    item.blob_uris.map((uri) => [uri, Buffer.from(pool[uri], "base64")]),
  );
  for (const [uri, payload] of Object.entries(item.blob_mutations ?? {})) {
    blobs.set(uri, Buffer.from(payload, "base64"));
  }
  return blobs;
}

export function applySceneFieldCase(
  scene: JsonRecord,
  item: SceneFieldCase,
): JsonRecord {
  const result = structuredClone(scene);
  for (const mutation of item.mutations) {
    let current: JsonRecord | unknown[] = result;
    for (const part of mutation.path.slice(0, -1)) {
      current = Array.isArray(current)
        ? current[part as number] as JsonRecord | unknown[]
        : current[part as string] as JsonRecord | unknown[];
    }
    const final = mutation.path.at(-1)!;
    if (mutation.operation === "delete") {
      if (Array.isArray(current)) delete current[final as number];
      else delete current[final as string];
    } else if (Array.isArray(current)) {
      current[final as number] = structuredClone(mutation.value);
    } else {
      current[final as string] = structuredClone(mutation.value);
    }
  }
  return item.recompute_revision ? withSceneRevision(result) : result;
}

export function sceneShapeFacts(scene: JsonRecord): SceneShapeFacts {
  const nodes = asRecords(scene.nodes);
  const definitionOccurrenceCounts: Record<string, number> = {};
  for (const node of nodes) {
    const definitionId = String(node.definition_id);
    definitionOccurrenceCounts[definitionId] =
      (definitionOccurrenceCounts[definitionId] ?? 0) + 1;
  }
  return {
    definition_count: asRecords(scene.definitions).length,
    definition_occurrence_counts: Object.fromEntries(
      Object.entries(definitionOccurrenceCounts).sort(([left], [right]) =>
        Buffer.compare(Buffer.from(left), Buffer.from(right))
      ),
    ),
    edge_asset_count: asRecords(scene.edge_assets).length,
    entity_asset_count: asRecords(scene.entity_assets).length,
    geometry_asset_count: asRecords(scene.geometry_assets).length,
    maximum_depth: Math.max(
      ...nodes.map((node) => {
        const source = asRecord(node.source);
        return Array.isArray(source.component_path) ? source.component_path.length : 0;
      }),
    ),
    node_count: nodes.length,
    root_node_ids: nodes
      .filter((node) => node.parent_node_id === null)
      .map((node) => String(node.node_id)),
  };
}
