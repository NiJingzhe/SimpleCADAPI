import {
  canonicalJsonBytes,
  computeSceneRevision,
  DuplicateKeyError,
  parseCanonicalJson,
  parseStrictJson,
  sha256,
} from "./canonical.js";
import { type GlbInfo, preflightGlb } from "./glb.js";
import { hasRootPointerPolicy, issue, pointer, report, type ValidationArtifact, type ValidationIssue, type ValidationReport } from "./report.js";
import { BASE_LIMITS, preflightResourceCount, type SceneResourceLimits } from "./resources.js";
import { composeRigidTransforms, rigidTransformsEqual } from "./transforms.js";
import type { ValidateFunction } from "ajv";
import {
  schemaErrors,
  validateConnectorBindingSchema,
  validateEntitiesSchema,
  validateNormalizedProductSchema,
  validatePresentationSchema,
  validateSceneSchema,
} from "./schema.js";

type JsonRecord = Record<string, unknown>;
type DocumentArtifact = Exclude<ValidationArtifact, "package" | "glb" | "zip">;

const collectionSortKeys: Record<string, string> = {
  definitions: "definition_id",
  nodes: "node_id",
  geometry_assets: "asset_id",
  edge_assets: "asset_id",
  entity_assets: "entity_asset_id",
  appearances: "appearance_id",
  connectors: "connector_snapshot_id",
  cameras: "camera_id",
  entities: "entity_id",
};
const setArrayKeys = new Set(["semantic_binding_ids", "evaluated_tags", "parent_entity_ids", "child_entity_ids"]);
const identifierArrayKeys = new Set([
  "child_entity_ids",
  "component_path",
  "evaluated_tags",
  "grounded_component_ids",
  "parent_entity_ids",
  "semantic_binding_ids",
]);
const sourcePathPattern = /^[A-Za-z0-9][A-Za-z0-9._/-]*\.py$/;
const operationSourceKeys = new Set([
  "assignment_targets",
  "call_text",
  "callsite_id",
  "column",
  "end_column",
  "end_line",
  "line",
  "path",
  "path_kind",
  "schema_version",
]);

function isRecord(value: unknown): value is JsonRecord {
  return value !== null && typeof value === "object" && !Array.isArray(value);
}

function utf8Compare(left: string, right: string): number {
  return Buffer.compare(Buffer.from(left, "utf8"), Buffer.from(right, "utf8"));
}

function parseInput(value: unknown, canonical: boolean): { value?: unknown; issues: ValidationIssue[] } {
  if (!(typeof value === "string" || value instanceof Uint8Array)) return { value, issues: [] };
  try {
    return { value: canonical ? parseCanonicalJson(value) : parseStrictJson(value), issues: [] };
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    let code: string;
    if (error instanceof DuplicateKeyError) code = "duplicate_json_key";
    else if (message.includes("BOM")) code = "bom_forbidden";
    else if (error instanceof TypeError && (message.toLowerCase().includes("utf") || message.includes("surrogate"))) code = "invalid_utf8";
    else if (message.includes("nesting")) code = "resource_limit_exceeded";
    else if (message.includes("canonical") && canonical) code = "noncanonical_json";
    else if (message.includes("finite") || message.includes("NaN") || message.includes("Infinity")) code = "nonfinite_json_number";
    else code = "schema_invalid";
    const phase = code === "resource_limit_exceeded" ? "budget" : code === "schema_invalid" ? "structure" : "parse";
    return { issues: [issue(code, "", message, phase)] };
  }
}

function structuralIssues(value: unknown, validator: ValidateFunction): ValidationIssue[] {
  return schemaErrors(validator, value).map((error) =>
    issue(
      "schema_invalid",
      error.instancePath,
      error.keyword === "additionalProperties" ? "unknown field is forbidden by the closed schema" : error.message ?? "schema validation failed",
      "structure",
    ),
  );
}

function walk(value: unknown): [readonly (string | number)[], unknown][] {
  const result: [readonly (string | number)[], unknown][] = [];
  const stack: [readonly (string | number)[], unknown][] = [[[], value]];
  while (stack.length > 0) {
    const current = stack.pop()!;
    result.push(current);
    const [path, child] = current;
    if (Array.isArray(child)) {
      for (let index = child.length - 1; index >= 0; index -= 1) stack.push([[...path, index], child[index]]);
    } else if (isRecord(child)) {
      const entries = Object.entries(child);
      for (let index = entries.length - 1; index >= 0; index -= 1) stack.push([[...path, entries[index][0]], entries[index][1]]);
    }
  }
  return result;
}

function hasUnpairedSurrogate(value: string): boolean {
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (next < 0xdc00 || next > 0xdfff) return true;
      index += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      return true;
    }
  }
  return false;
}

function isMetadataPath(path: readonly (string | number)[]): boolean {
  return path.some((part) => part === "metadata" || part === "sdk_metadata");
}

function isIdentifierPath(path: readonly (string | number)[]): boolean {
  if (path.length === 0) return false;
  const field = path.at(-1);
  if (typeof field === "string" && (field.endsWith("_id") || ["definition_ref", "source_element_id", "topo_id"].includes(field))) {
    return true;
  }
  return path.length >= 2 && typeof field === "number" && typeof path.at(-2) === "string" && identifierArrayKeys.has(path.at(-2) as string);
}

function isUriPath(path: readonly (string | number)[]): boolean {
  const field = path.at(-1);
  return typeof field === "string" && (field === "uri" || field.endsWith("_uri"));
}

function serializedSize(value: unknown): number | null {
  if (typeof value === "string") return Buffer.byteLength(value, "utf8");
  if (value instanceof Uint8Array) return value.byteLength;
  try {
    return canonicalJsonBytes(value).byteLength;
  } catch {
    return null;
  }
}

function serializedSizeIssues(value: unknown, artifact: ValidationArtifact, limits: SceneResourceLimits): ValidationIssue[] {
  const size = serializedSize(value);
  const limit = artifact === "scene"
    ? limits.scene_json_bytes
    : artifact === "entities"
      ? limits.entity_json_bytes
      : artifact === "presentation"
        ? limits.presentation_json_bytes
        : limits.one_member_bytes;
  return size !== null && size > limit
    ? [issue("resource_limit_exceeded", "", `${artifact} JSON bytes exceed resource limit`, "budget")]
    : [];
}

export function jsonResourceIssues(value: unknown, limits: SceneResourceLimits = BASE_LIMITS): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  for (const [path, child] of walk(value)) {
    const jsonPointer = pointer(path);
    if (path.length > limits.json_depth) {
      issues.push(issue("resource_limit_exceeded", jsonPointer, "JSON nesting exceeds resource limit", "budget"));
    }
    if (isRecord(child)) {
      for (const key of Object.keys(child)) {
        const keyPointer = pointer([...path, key]);
        if (hasUnpairedSurrogate(key)) {
          issues.push(issue("invalid_utf8", keyPointer, "object key contains an unpaired surrogate", "parse"));
          continue;
        }
        const keyBytes = Buffer.byteLength(key, "utf8");
        if (keyBytes > limits.json_string_bytes) {
          issues.push(issue("resource_limit_exceeded", keyPointer, "JSON object key exceeds resource limit", "budget"));
        }
        if (isMetadataPath(path) && keyBytes > limits.structural_id_bytes) {
          issues.push(issue("resource_limit_exceeded", keyPointer, "metadata key exceeds structural ID resource limit", "budget"));
        }
      }
    }
    if (typeof child === "number") {
      if (!Number.isFinite(child)) {
        issues.push(issue("nonfinite_json_number", jsonPointer, "JSON number must be finite", "parse"));
      }
    } else if (typeof child === "string") {
      if (hasUnpairedSurrogate(child)) {
        issues.push(issue("invalid_utf8", jsonPointer, "string contains an unpaired surrogate", "parse"));
      } else {
        const bytes = Buffer.byteLength(child, "utf8");
        if (bytes > limits.json_string_bytes) {
          issues.push(issue("resource_limit_exceeded", jsonPointer, "JSON string exceeds resource limit", "budget"));
        }
        if (isUriPath(path) && bytes > limits.uri_bytes) {
          issues.push(issue("resource_limit_exceeded", jsonPointer, "URI exceeds resource limit", "budget"));
        }
        if (isIdentifierPath(path) && bytes > limits.structural_id_bytes) {
          issues.push(issue("resource_limit_exceeded", jsonPointer, "identifier exceeds structural ID resource limit", "budget"));
        }
      }
    }
  }
  return issues;
}

export function resourceCountIssues(
  value: unknown,
  artifact: DocumentArtifact,
  limits: SceneResourceLimits = BASE_LIMITS,
): ValidationIssue[] {
  if (!isRecord(value)) return [];
  const issues: ValidationIssue[] = [];
  let collections: readonly (readonly [string, keyof SceneResourceLimits])[] = [];
  if (artifact === "scene") {
    collections = [
      ["definitions", "definitions"], ["nodes", "nodes"],
      ["geometry_assets", "assets_per_kind"], ["edge_assets", "assets_per_kind"], ["entity_assets", "assets_per_kind"],
      ["appearances", "appearances"], ["connectors", "connectors"], ["cameras", "cameras"],
    ];
  } else if (artifact === "entities") {
    collections = [
      ["entities", "entities_per_sidecar"],
      ["face_groups", "entities_per_sidecar"],
      ["edge_groups", "entities_per_sidecar"],
    ];
  } else if (artifact === "presentation") {
    collections = [["node_overrides", "nodes"], ["appearances", "appearances"], ["cameras", "cameras"]];
  }
  for (const [field, limitName] of collections) {
    const records = value[field];
    if (Array.isArray(records)) {
      try {
        preflightResourceCount(records.length, limitName, limits);
      } catch {
        issues.push(issue("resource_limit_exceeded", `/${field}`, `${field} count exceeds resource limit`, "budget"));
      }
    }
  }
  if (artifact === "scene") {
    const nodes = Array.isArray(value.nodes) ? value.nodes : [];
    nodes.forEach((node, index) => {
      const source = isRecord(node) && isRecord(node.source) ? node.source : null;
      if (source !== null && Array.isArray(source.component_path) && source.component_path.length > limits.hierarchy_depth) {
        issues.push(issue("resource_limit_exceeded", `/nodes/${index}/source/component_path`, "hierarchy depth exceeds resource limit", "budget"));
      }
    });
    const connectors = Array.isArray(value.connectors) ? value.connectors.filter(isRecord) : [];
    const forwardEdges = new Map<unknown, unknown>();
    for (const connector of connectors) {
      if (connector.anchor_kind === "forwarded" && isRecord(connector.forwarded_from)) {
        forwardEdges.set(connector.connector_snapshot_id, connector.forwarded_from.source_connector_snapshot_id);
      }
    }
    for (const start of forwardEdges.keys()) {
      const seen = new Set<unknown>();
      let current: unknown = start;
      let depth = 0;
      while (forwardEdges.has(current) && !seen.has(current)) {
        seen.add(current);
        current = forwardEdges.get(current);
        depth += 1;
        if (depth > limits.forwarded_connector_depth) {
          issues.push(issue("resource_limit_exceeded", "/connectors", "forwarded connector depth exceeds resource limit", "budget"));
          break;
        }
      }
    }
  }
  return issues;
}

function arrayOrderIssues(value: JsonRecord): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  for (const [path, child] of walk(value)) {
    const key = path.at(-1);
    if (typeof key === "string" && setArrayKeys.has(key) && Array.isArray(child) && child.every((item) => typeof item === "string")) {
      const expected = [...new Set(child)].sort(utf8Compare);
      if (child.length !== expected.length || child.some((item, index) => item !== expected[index])) {
        issues.push(issue("array_order_invalid", pointer(path), "set-like array is not sorted and unique"));
      }
    }
  }
  for (const [collection, idKey] of Object.entries(collectionSortKeys)) {
    const records = value[collection];
    if (Array.isArray(records) && records.every((item) => isRecord(item) && typeof item[idKey] === "string")) {
      const ids = records.map((item) => (item as JsonRecord)[idKey] as string);
      const expected = [...new Set(ids)].sort(utf8Compare);
      if (ids.length !== expected.length || ids.some((id, index) => id !== expected[index])) {
        issues.push(issue("array_order_invalid", `/${collection}`, `${collection} is not sorted and unique by ${idKey}`));
      }
    }
  }
  return issues;
}

function vec3(value: unknown): value is [number, number, number] {
  return Array.isArray(value) && value.length === 3 && value.every((item) => typeof item === "number" && Number.isFinite(item));
}

function transformIssue(value: unknown, path: string): ValidationIssue | null {
  if (!isRecord(value) || !vec3(value.origin) || !vec3(value.x_axis) || !vec3(value.y_axis) || !vec3(value.z_axis)) return null;
  const origin = value.origin;
  const axes = [value.x_axis, value.y_axis, value.z_axis];
  if (origin.some((component) => Math.abs(component) > 1e12)) return issue("transform_invalid", path, "transform origin exceeds the scene coordinate limit");
  const dot = (left: readonly number[], right: readonly number[]) => left.reduce((sum, item, index) => sum + item * right[index], 0);
  if (axes.some((axis) => Math.abs(Math.sqrt(dot(axis, axis)) - 1) > 1e-12)) return issue("transform_invalid", path, "transform axes must be unit vectors within 1e-12");
  if (Math.abs(dot(axes[0], axes[1])) > 1e-12 || Math.abs(dot(axes[0], axes[2])) > 1e-12 || Math.abs(dot(axes[1], axes[2])) > 1e-12) return issue("transform_invalid", path, "transform axes must be pairwise orthogonal within 1e-12");
  const cross = [axes[0][1] * axes[1][2] - axes[0][2] * axes[1][1], axes[0][2] * axes[1][0] - axes[0][0] * axes[1][2], axes[0][0] * axes[1][1] - axes[0][1] * axes[1][0]];
  if (cross.some((component, index) => Math.abs(component - axes[2][index]) > 1e-12)) return issue("transform_invalid", path, "z_axis must equal cross(x_axis, y_axis) within 1e-12");
  return null;
}

function analyticIssues(geometry: unknown, path: string): ValidationIssue[] {
  if (!isRecord(geometry)) return [];
  const directionFields: Record<string, string[]> = {
    line: ["direction"], circle: ["normal", "x_direction"], ellipse: ["normal", "x_direction"],
    plane: ["normal", "x_direction"], cylinder: ["axis", "x_direction"], cone: ["axis", "x_direction"],
    sphere: ["axis", "x_direction"], torus: ["axis", "x_direction"],
  };
  const coordinateFields: Record<string, string[]> = {
    point: ["position"], line: ["origin"], circle: ["center"], ellipse: ["center"],
    plane: ["origin"], cylinder: ["origin"], cone: ["origin"], sphere: ["center"],
    torus: ["center"],
  };
  const type = typeof geometry.type === "string" ? geometry.type : "";
  const names = directionFields[type] ?? [];
  const issues: ValidationIssue[] = [];
  for (const name of coordinateFields[type] ?? []) {
    const coordinate = geometry[name];
    if (vec3(coordinate) && coordinate.some((component) => Math.abs(component) > 1e12)) {
      issues.push(issue("analytic_geometry_invalid", `${path}/${name}`, "analytic coordinate exceeds the scene coordinate limit"));
    }
  }
  if (!names.every((name) => vec3(geometry[name]))) return issues;
  const vectors = names.map((name) => geometry[name] as [number, number, number]);
  vectors.forEach((vector, index) => {
    const norm = Math.sqrt(vector.reduce((sum, component) => sum + component * component, 0));
    if (Math.abs(norm - 1) > 1e-12) issues.push(issue("analytic_geometry_invalid", `${path}/${names[index]}`, "analytic direction must be a unit vector within 1e-12"));
  });
  if (vectors.length === 2 && Math.abs(vectors[0].reduce((sum, component, index) => sum + component * vectors[1][index], 0)) > 1e-12) {
    issues.push(issue("analytic_geometry_invalid", path, "analytic axis and x_direction must be orthogonal within 1e-12"));
  }
  return issues;
}

function boundsIssues(bounds: unknown, path: string, point?: unknown): ValidationIssue[] {
  if (!isRecord(bounds) || !vec3(bounds.min) || !vec3(bounds.max)) return [];
  const minimum = bounds.min;
  const maximum = bounds.max;
  const issues: ValidationIssue[] = [];
  if (minimum.some((low, index) => low > maximum[index])) {
    issues.push(issue("bounds_invalid", path, "bounds min exceeds max"));
  }
  if ([...minimum, ...maximum].some((component) => Math.abs(component) > 1e12)) {
    issues.push(issue("bounds_invalid", path, "bounds exceed the scene coordinate limit"));
  }
  if (vec3(point)) {
    const maxAbs = Math.max(1, ...minimum.map(Math.abs), ...maximum.map(Math.abs), ...point.map(Math.abs));
    const epsilon = Math.max(1e-9, 1e-12 * maxAbs);
    if (point.some((value, index) => value < minimum[index] - epsilon || value > maximum[index] + epsilon)) {
      issues.push(issue("bounds_invalid", path, "point or centroid is outside bounds"));
    }
  }
  return issues;
}

function encodeSegment(value: string): string {
  let result = "";
  for (const byte of Buffer.from(value, "utf8")) {
    const safe =
      (byte >= 0x41 && byte <= 0x5a) ||
      (byte >= 0x61 && byte <= 0x7a) ||
      (byte >= 0x30 && byte <= 0x39) ||
      byte === 0x2d || byte === 0x2e || byte === 0x5f || byte === 0x7e;
    result += safe ? String.fromCharCode(byte) : `%${byte.toString(16).toUpperCase().padStart(2, "0")}`;
  }
  return result;
}

function rootIdFromDefinition(definition: JsonRecord): unknown {
  return isRecord(definition.source) ? definition.source.root_id : undefined;
}

function setsEqual(left: ReadonlySet<unknown>, right: ReadonlySet<unknown>): boolean {
  return left.size === right.size && [...left].every((value) => right.has(value));
}

function sceneSemanticIssues(scene: JsonRecord): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (scene.revision !== computeSceneRevision(scene)) issues.push(issue("revision_mismatch", "/revision", "scene revision does not match canonical draft hash"));
  const source = isRecord(scene.source) ? scene.source : {};
  const sourceKind = source.kind;
  const graphId = source.graph_id;
  const sourceId = source.source_id;
  const options = isRecord(scene.compile_options) ? scene.compile_options : {};
  const presentationSource = scene.presentation_source;
  const embedSource = options.embed_source;
  const embedded = Object.hasOwn(source, "embedded_artifact_uri");
  if (sourceKind === "manual" && (embedSource === true || embedded)) {
    issues.push(issue("source_matrix_invalid", "/source", "manual source cannot be embedded"));
  } else if ((sourceKind === "model" || sourceKind === "imported") && embedSource !== embedded) {
    issues.push(issue("source_matrix_invalid", "/source", "embed_source does not match source embedding fields"));
  }
  const sourceFiles = Array.isArray(source.source_files) ? source.source_files.filter(isRecord) : [];
  const sourcePaths = sourceFiles.map((record) => String(record.path ?? ""));
  const expectedSourcePaths = [...new Set(sourcePaths)].sort(utf8Compare);
  if (sourcePaths.some((path, index) => path !== expectedSourcePaths[index]) || sourcePaths.length !== expectedSourcePaths.length) {
    issues.push(issue("array_order_invalid", "/source/source_files", "source_files is not sorted and unique by path"));
  }
  const casefoldSourcePaths = new Map<string, string>();
  sourceFiles.forEach((record, index) => {
    if (typeof record.path === "string") {
      const segments = record.path.split("/");
      if (!sourcePathPattern.test(record.path) || segments.some((segment) => segment === "" || segment === "." || segment === "..")) {
        issues.push(issue("source_matrix_invalid", `/source/source_files/${index}/path`, "source file path is not archive-safe"));
      }
      const folded = record.path.toLowerCase();
      const previous = casefoldSourcePaths.get(folded);
      if (previous !== undefined && previous !== record.path) {
        issues.push(issue("source_matrix_invalid", `/source/source_files/${index}/path`, "source file paths collide case-insensitively"));
      } else {
        casefoldSourcePaths.set(folded, record.path);
      }
      if (record.uri !== `sources/${record.path}`) {
        issues.push(issue("source_matrix_invalid", `/source/source_files/${index}/uri`, "source file URI does not preserve the project-relative path"));
      }
    }
  });
  const embedPresentation = options.embed_presentation;
  if ((presentationSource === null || presentationSource === undefined) && embedPresentation === true) {
    issues.push(issue("source_matrix_invalid", "/compile_options/embed_presentation", "presentation embedding requires presentation_source"));
  }
  if (
    isRecord(presentationSource) &&
    embedPresentation !== Object.hasOwn(presentationSource, "embedded_artifact_uri")
  ) {
    issues.push(issue("source_matrix_invalid", "/presentation_source", "embed_presentation does not match presentation embedding fields"));
  }

  const definitions = Array.isArray(scene.definitions) ? scene.definitions.filter(isRecord) : [];
  const nodes = Array.isArray(scene.nodes) ? scene.nodes.filter(isRecord) : [];
  const appearances = Array.isArray(scene.appearances) ? scene.appearances.filter(isRecord) : [];
  const definitionMap = new Map<unknown, JsonRecord>(definitions.map((record) => [record.definition_id, record]));
  const nodeMap = new Map<unknown, JsonRecord>(nodes.map((record) => [record.node_id, record]));
  const appearanceMap = new Map<unknown, JsonRecord>(appearances.map((record) => [record.appearance_id, record]));
  const geometryMap = new Map<unknown, JsonRecord>((Array.isArray(scene.geometry_assets) ? scene.geometry_assets : []).filter(isRecord).map((record) => [record.asset_id, record]));
  const edgeMap = new Map<unknown, JsonRecord>((Array.isArray(scene.edge_assets) ? scene.edge_assets : []).filter(isRecord).map((record) => [record.asset_id, record]));
  const entityMap = new Map<unknown, JsonRecord>((Array.isArray(scene.entity_assets) ? scene.entity_assets : []).filter(isRecord).map((record) => [record.entity_asset_id, record]));
  const validSources: Record<string, Record<string, string>> = {
    model: { part: "product_model", assembly: "product_model", shape: "model_output" },
    manual: { part: "product_manual", assembly: "product_manual", shape: "manual" },
    imported: { shape: "imported" },
  };
  definitions.forEach((definition, index) => {
    const path = `/definitions/${index}`;
    const kind = definition.kind;
    const nested = isRecord(definition.source) ? definition.source : {};
    const nestedKind = nested.kind;
    const rootId = nested.root_id;
    const validSource = typeof sourceKind === "string" && typeof kind === "string"
      ? validSources[sourceKind]?.[kind]
      : undefined;
    if (nestedKind !== validSource) {
      issues.push(issue("source_matrix_invalid", `${path}/source`, "definition source is incompatible with scene and definition kinds"));
    }
    if ((nestedKind === "product_model" || nestedKind === "model_output") && nested.graph_id !== graphId) {
      issues.push(issue("source_matrix_invalid", `${path}/source/graph_id`, "definition graph_id differs from scene graph_id"));
    }
    if (nestedKind === "manual" && nested.source_id !== sourceId) {
      issues.push(issue("source_matrix_invalid", `${path}/source/source_id`, "definition manual source_id differs from scene source_id"));
    }
    let expectedId: string;
    if (nestedKind === "product_model" || nestedKind === "product_manual") {
      const expectedSemantic = kind === "part" ? "Part" : "Assembly";
      if (nested.semantic_type !== expectedSemantic) {
        issues.push(issue("source_matrix_invalid", `${path}/source/semantic_type`, "semantic_type differs from definition kind"));
      }
      expectedId = `definition/${String(rootId)}/${String(kind)}/${encodeSegment(String(nested.semantic_id ?? ""))}`;
    } else if (nestedKind === "model_output") {
      expectedId = `definition/${String(rootId)}/shape/model/${encodeSegment(String(nested.graph_id ?? ""))}/${encodeSegment(String(nested.node_id ?? ""))}/${String(nested.output_slot)}`;
    } else if (nestedKind === "imported") {
      expectedId = `definition/${String(rootId)}/shape/imported/${encodeSegment(String(nested.source_element_id ?? ""))}`;
    } else {
      expectedId = `definition/${String(rootId)}/shape/manual/${encodeSegment(String(nested.source_id ?? ""))}`;
    }
    if (definition.definition_id !== expectedId) {
      issues.push(issue("source_matrix_invalid", `${path}/definition_id`, "definition_id does not match its source-derived structural ID"));
    }
    for (const [field, registry] of [
      ["geometry_asset_id", geometryMap],
      ["edge_asset_id", edgeMap],
      ["entity_asset_id", entityMap],
      ["appearance_id", appearanceMap],
    ] as const) {
      const reference = definition[field];
      if (reference !== null && reference !== undefined && !registry.has(reference)) {
        issues.push(issue("reference_missing", `${path}/${field}`, `referenced ${field} does not exist`));
      }
    }
  });

  const roots: JsonRecord[] = [];
  const siblingOrders = new Map<unknown, unknown[]>();
  const referencedDefinitions = new Set<unknown>();
  nodes.forEach((node, index) => {
    const path = `/nodes/${index}`;
    const definition = definitionMap.get(node.definition_id);
    if (definition === undefined) {
      issues.push(issue("reference_missing", `${path}/definition_id`, "node definition does not exist"));
      return;
    }
    referencedDefinitions.add(node.definition_id);
    const nodeSource = isRecord(node.source) ? node.source : {};
    const nodeKind = nodeSource.kind;
    const rootId = nodeSource.root_id;
    const expectedNodeKind = definition.kind === "part" || definition.kind === "assembly" ? "product_occurrence" : "shape_root";
    if (nodeKind !== expectedNodeKind || rootId !== rootIdFromDefinition(definition)) {
      issues.push(issue("source_matrix_invalid", `${path}/source`, "node source kind/root does not match definition"));
    }
    let expectedNodeId: string;
    let expectedParent: string | null;
    if (nodeKind === "product_occurrence") {
      const componentPath = Array.isArray(nodeSource.component_path) ? nodeSource.component_path : [];
      const encodedPath = componentPath.map((segment) => `/${encodeSegment(String(segment))}`).join("");
      const encodedParentPath = componentPath.slice(0, -1).map((segment) => `/${encodeSegment(String(segment))}`).join("");
      expectedNodeId = `instance/${String(rootId)}${encodedPath}`;
      expectedParent = componentPath.length === 0 ? null : `instance/${String(rootId)}${encodedParentPath}`;
    } else {
      expectedNodeId = `instance/${String(rootId)}`;
      expectedParent = null;
    }
    if (node.node_id !== expectedNodeId) {
      issues.push(issue("hierarchy_invalid", `${path}/node_id`, "node_id does not match source-derived structural ID"));
    }
    if (node.parent_node_id !== expectedParent) {
      issues.push(issue("hierarchy_invalid", `${path}/parent_node_id`, "parent_node_id does not match component path"));
    }
    if (node.parent_node_id === null) roots.push(node);
    else if (!nodeMap.has(node.parent_node_id)) {
      issues.push(issue("reference_missing", `${path}/parent_node_id`, "parent node does not exist"));
    }
    const orders = siblingOrders.get(node.parent_node_id) ?? [];
    orders.push(node.order);
    siblingOrders.set(node.parent_node_id, orders);
    const override = node.appearance_override_id;
    if (node.selectable !== true) {
      issues.push(issue("source_matrix_invalid", `${path}/selectable`, "node selectability must use the deterministic true default"));
    }
    if (presentationSource === null || presentationSource === undefined) {
      if (node.visible !== true) {
        issues.push(issue("source_matrix_invalid", `${path}/visible`, "node visibility requires presentation_source"));
      }
      if (override !== null && override !== undefined) {
        issues.push(issue("source_matrix_invalid", `${path}/appearance_override_id`, "appearance override requires presentation_source"));
      }
    }
    if (override !== null && override !== undefined && !appearanceMap.has(override)) {
      issues.push(issue("reference_missing", `${path}/appearance_override_id`, "appearance override does not exist"));
    }
    if (definition.kind === "assembly" && override !== null && override !== undefined) {
      issues.push(issue("source_matrix_invalid", `${path}/appearance_override_id`, "assembly occurrence cannot carry appearance override"));
    }
    const transform = transformIssue(node.transform, `${path}/transform`);
    if (transform !== null) issues.push(transform);
  });
  for (const [parent, orders] of siblingOrders) {
    if (
      orders.every((order) => typeof order === "number" && Number.isInteger(order)) &&
      [...orders].sort((left, right) => (left as number) - (right as number)).some((order, index) => order !== index)
    ) {
      issues.push(issue("hierarchy_invalid", "/nodes", `sibling order under ${String(parent)} is not continuous`));
    }
  }
  const rootIds = roots.map((root) => isRecord(root.source) ? root.source.root_id : undefined);
  const expectedRoots = [...rootIds].sort((left, right) => utf8Compare(String(left), String(right)));
  const actualRoots = [...roots]
    .sort((left, right) => (left.order as number) - (right.order as number))
    .map((root) => isRecord(root.source) ? root.source.root_id : undefined);
  if (actualRoots.some((rootId, index) => rootId !== expectedRoots[index])) {
    issues.push(issue("hierarchy_invalid", "/nodes", "root order does not match unsigned UTF-8 root_id order"));
  }
  const definitionIds = new Set(definitionMap.keys());
  if (definitionIds.size > 0 || nodeMap.size > 0) {
    if (!setsEqual(referencedDefinitions, definitionIds)) {
      issues.push(issue("hierarchy_invalid", "/nodes", "every definition must be instantiated by at least one node"));
    }
    const definitionRootIds = new Set([...definitionMap.values()].map(rootIdFromDefinition));
    if ([...definitionRootIds].some((rootId) => roots.filter((root) => isRecord(root.source) && root.source.root_id === rootId).length !== 1)) {
      issues.push(issue("hierarchy_invalid", "/nodes", "each definition root_id must have exactly one root occurrence"));
    }
  }

  const usedAssets = new Set<unknown>();
  for (const definition of definitions) {
    for (const field of ["geometry_asset_id", "edge_asset_id", "entity_asset_id"]) {
      const reference = definition[field];
      if (reference !== null && reference !== undefined) usedAssets.add(reference);
    }
  }
  const declaredAssets = new Set<unknown>([...geometryMap.keys(), ...edgeMap.keys(), ...entityMap.keys()]);
  if (!setsEqual(usedAssets, declaredAssets)) {
    issues.push(issue("reference_missing", "/definitions", "asset records must be referenced exactly by definitions"));
  }
  for (const [collection, uriKind] of [["geometry_assets", "geometry"], ["edge_assets", "edges"]] as const) {
    const assets = Array.isArray(scene[collection]) ? (scene[collection] as unknown[]).filter(isRecord) : [];
    assets.forEach((asset, index) => {
      const path = `/${collection}/${index}`;
      if (asset.asset_id !== asset.content_hash) {
        issues.push(issue("source_matrix_invalid", `${path}/asset_id`, "asset_id must equal content_hash"));
      }
      const assetId = String(asset.asset_id ?? "");
      const digest = assetId.startsWith("sha256:") ? assetId.slice("sha256:".length) : assetId;
      if (asset.uri !== `${uriKind}/sha256-${digest}.glb`) {
        issues.push(issue("source_matrix_invalid", `${path}/uri`, "asset URI does not match content hash"));
      }
      const tessellation = isRecord(asset.tessellation) ? asset.tessellation : {};
      if (tessellation.linear_tolerance !== options.linear_tolerance) {
        issues.push(issue("source_matrix_invalid", `${path}/tessellation/linear_tolerance`, "asset tolerance differs from compile options"));
      }
      if (collection === "geometry_assets" && tessellation.angular_tolerance !== options.angular_tolerance) {
        issues.push(issue("source_matrix_invalid", `${path}/tessellation/angular_tolerance`, "asset tolerance differs from compile options"));
      }
      issues.push(...boundsIssues(asset.scene_local_bounds, `${path}/scene_local_bounds`));
    });
  }
  const entityAssets = Array.isArray(scene.entity_assets) ? scene.entity_assets.filter(isRecord) : [];
  entityAssets.forEach((asset, index) => {
    const path = `/entity_assets/${index}`;
    if (asset.entity_asset_id !== asset.content_hash) {
      issues.push(issue("source_matrix_invalid", `${path}/entity_asset_id`, "entity_asset_id must equal content_hash"));
    }
    const assetId = String(asset.entity_asset_id ?? "");
    const digest = assetId.startsWith("sha256:") ? assetId.slice("sha256:".length) : assetId;
    if (asset.uri !== `entities/sha256-${digest}.json`) {
      issues.push(issue("source_matrix_invalid", `${path}/uri`, "entity URI does not match content hash"));
    }
  });
  appearances.forEach((appearance, index) => {
    const path = `/appearances/${index}`;
    const draft = { ...appearance };
    delete draft.appearance_id;
    const expected = `appearance/evaluated/${sha256(canonicalJsonBytes(draft)).slice("sha256:".length)}`;
    if (appearance.appearance_id !== expected) {
      issues.push(issue("source_matrix_invalid", `${path}/appearance_id`, "appearance_id does not match content-derived identity"));
    }
    const appearanceSource = appearance.source;
    if (isRecord(appearanceSource)) {
      if (appearanceSource.kind === "product_material" && sourceKind !== "model" && sourceKind !== "manual") {
        issues.push(issue("source_matrix_invalid", `${path}/source`, "product material source is incompatible with scene source"));
      }
      if (
        appearanceSource.kind === "product_material" &&
        !definitions.some((definition) =>
          definition.kind === "part" &&
          definition.appearance_id === appearance.appearance_id &&
          rootIdFromDefinition(definition) === appearanceSource.root_id
        )
      ) {
        issues.push(issue("source_matrix_invalid", `${path}/source/root_id`, "product material appearance provenance does not match a Part definition root"));
      }
      if (
        appearanceSource.kind === "presentation" &&
        (!isRecord(presentationSource) || appearanceSource.presentation_id !== presentationSource.presentation_id)
      ) {
        issues.push(issue("source_matrix_invalid", `${path}/source`, "presentation appearance source does not match presentation_source"));
      }
    }
  });

  const connectors = Array.isArray(scene.connectors) ? scene.connectors.filter(isRecord) : [];
  if (sourceKind === "imported" && connectors.length > 0) {
    issues.push(issue("source_matrix_invalid", "/connectors", "imported scene connectors must be empty"));
  }
  const connectorMap = new Map<unknown, JsonRecord>(connectors.map((record) => [record.connector_snapshot_id, record]));
  const connectorIdsByOwner = new Map<unknown, Set<unknown>>();
  const forwardEdges = new Map<unknown, unknown>();
  connectors.forEach((connector, index) => {
    const path = `/connectors/${index}`;
    const owner = definitionMap.get(connector.owner_definition_id);
    if (owner === undefined) {
      issues.push(issue("reference_missing", `${path}/owner_definition_id`, "connector owner definition does not exist"));
      return;
    }
    const ownerIds = connectorIdsByOwner.get(connector.owner_definition_id) ?? new Set<unknown>();
    if (ownerIds.has(connector.connector_id)) {
      issues.push(issue("id_duplicate", `${path}/connector_id`, "connector_id is duplicated within owner definition"));
    }
    ownerIds.add(connector.connector_id);
    connectorIdsByOwner.set(connector.owner_definition_id, ownerIds);
    const ownerSource = isRecord(owner.source) ? owner.source : {};
    const ownerSemantic = ownerSource.semantic_id === undefined || ownerSource.semantic_id === null
      ? "None"
      : String(ownerSource.semantic_id);
    const expectedSnapshot = `connector/${String(ownerSource.root_id)}/${String(owner.kind)}/${encodeSegment(ownerSemantic)}/${encodeSegment(String(connector.connector_id ?? ""))}`;
    if (connector.connector_snapshot_id !== expectedSnapshot) {
      issues.push(issue("connector_invalid", `${path}/connector_snapshot_id`, "connector snapshot ID does not match owner and connector IDs"));
    }
    const anchorKind = connector.anchor_kind;
    if (anchorKind === "geometry" && owner.kind !== "part") {
      issues.push(issue("connector_invalid", `${path}/owner_definition_id`, "geometry connector owner must be a Part"));
    }
    if (anchorKind === "placement" && owner.kind !== "part" && owner.kind !== "assembly") {
      issues.push(issue("connector_invalid", `${path}/owner_definition_id`, "connector owner must be a Product definition"));
    }
    if (anchorKind === "forwarded" && owner.kind !== "assembly") {
      issues.push(issue("connector_invalid", `${path}/owner_definition_id`, "forwarded connector owner must be an Assembly"));
    }
    const connectorSource = connector.source;
    if (sourceKind === "model") {
      if (!isRecord(connectorSource) || connectorSource.kind !== "model_operation" || connectorSource.graph_id !== graphId) {
        issues.push(issue("connector_invalid", `${path}/source`, "model connector must use the scene graph model_operation source"));
      } else if (connectorSource.output_slot !== 0) {
        issues.push(issue("connector_invalid", `${path}/source/output_slot`, "connector producer output_slot must be 0"));
      }
    } else if (
      sourceKind === "manual" &&
      (!isRecord(connectorSource) ||
        Object.keys(connectorSource).length !== 2 ||
        connectorSource.kind !== "manual" ||
        connectorSource.source_id !== sourceId)
    ) {
      issues.push(issue("connector_invalid", `${path}/source`, "manual connector source must equal the top-level source_id"));
    }
    const transform = transformIssue(connector.local_transform, `${path}/local_transform`);
    if (transform !== null) issues.push(transform);
    if (anchorKind === "forwarded") {
      const forwarded = isRecord(connector.forwarded_from) ? connector.forwarded_from : {};
      const sourceSnapshot = forwarded.source_connector_snapshot_id;
      const sourceConnector = connectorMap.get(sourceSnapshot);
      if (
        sourceConnector === undefined ||
        sourceConnector.owner_definition_id !== forwarded.source_definition_id ||
        sourceConnector.connector_id !== forwarded.source_connector_id
      ) {
        issues.push(issue("connector_invalid", `${path}/forwarded_from`, "forwarded connector source snapshot ownership is invalid"));
      }
      forwardEdges.set(connector.connector_snapshot_id, sourceSnapshot);
      if (forwarded.offset !== null && forwarded.offset !== undefined) {
        const offset = transformIssue(forwarded.offset, `${path}/forwarded_from/offset`);
        if (offset !== null) issues.push(offset);
      }
      if (owner.kind === "assembly") {
        const ownerNodes = nodes.filter((node) =>
          node.definition_id === connector.owner_definition_id &&
          isRecord(node.source) &&
          node.source.kind === "product_occurrence"
        );
        const sourceChildren: JsonRecord[] = [];
        for (const ownerNode of ownerNodes) {
          const ownerNodeSource = ownerNode.source as JsonRecord;
          const expectedPath = [
            ...(Array.isArray(ownerNodeSource.component_path) ? ownerNodeSource.component_path : []),
            forwarded.source_component_id,
          ];
          const matches = nodes.filter((node) =>
            isRecord(node.source) &&
            node.source.kind === "product_occurrence" &&
            node.source.root_id === ownerNodeSource.root_id &&
            Array.isArray(node.source.component_path) &&
            node.source.component_path.length === expectedPath.length &&
            node.source.component_path.every((component, componentIndex) => component === expectedPath[componentIndex]) &&
            node.parent_node_id === ownerNode.node_id
          );
          if (matches.length !== 1 || matches[0].definition_id !== forwarded.source_definition_id) {
            issues.push(issue("connector_invalid", `${path}/forwarded_from`, "forwarded connector source component is not one exact direct child"));
          } else {
            sourceChildren.push(matches[0]);
          }
        }
        if (sourceChildren.length > 1) {
          const expected = canonicalJsonBytes(sourceChildren[0].transform);
          if (sourceChildren.slice(1).some((child) => !canonicalJsonBytes(child.transform).equals(expected))) {
            issues.push(issue("connector_invalid", `${path}/forwarded_from`, "forwarded connector source child transforms differ between owner occurrences"));
          }
        }
        if (sourceChildren.length > 0 && sourceConnector !== undefined) {
          const childTransform = sourceChildren[0].transform;
          const sourceTransform = sourceConnector.local_transform;
          const offset = forwarded.offset ?? {
            origin: [0, 0, 0],
            x_axis: [1, 0, 0],
            y_axis: [0, 1, 0],
            z_axis: [0, 0, 1],
          };
          if (
            isRecord(childTransform) && transformIssue(childTransform, "") === null &&
            isRecord(sourceTransform) && transformIssue(sourceTransform, "") === null &&
            isRecord(offset) && transformIssue(offset, "") === null &&
            isRecord(connector.local_transform) && transformIssue(connector.local_transform, "") === null
          ) {
            const expected = composeRigidTransforms(composeRigidTransforms(childTransform, sourceTransform), offset);
            if (!rigidTransformsEqual(connector.local_transform, expected)) {
              issues.push(issue("connector_invalid", `${path}/local_transform`, "forwarded connector transform does not match child, source, and offset composition"));
            }
          }
        }
      }
    }
  });
  for (const start of forwardEdges.keys()) {
    const seen = new Set<unknown>();
    let current: unknown = start;
    while (forwardEdges.has(current)) {
      if (seen.has(current)) {
        issues.push(issue("connector_invalid", "/connectors", "forwarded connector graph contains a cycle"));
        break;
      }
      seen.add(current);
      current = forwardEdges.get(current);
    }
  }
  const cameras = Array.isArray(scene.cameras) ? scene.cameras.filter(isRecord) : [];
  cameras.forEach((camera, index) => {
    const path = `/cameras/${index}`;
    if (presentationSource === null || presentationSource === undefined) {
      issues.push(issue("source_matrix_invalid", path, "evaluated scene camera requires presentation_source"));
    }
    if (camera.parent_node_id !== null && camera.parent_node_id !== undefined && !nodeMap.has(camera.parent_node_id)) {
      issues.push(issue("reference_missing", `${path}/parent_node_id`, "camera parent node does not exist"));
    }
    if (typeof camera.near === "number" && typeof camera.far === "number" && camera.far <= camera.near) {
      issues.push(issue("bounds_invalid", `${path}/far`, "camera far must exceed near"));
    }
    const transform = transformIssue(camera.transform, `${path}/transform`);
    if (transform !== null) issues.push(transform);
  });
  return issues;
}

function entitySemanticIssues(asset: JsonRecord): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const entityValues = Array.isArray(asset.entities) ? asset.entities : [];
  const entities = entityValues.filter(isRecord);
  const byId = new Map<unknown, JsonRecord>(entities.map((entity) => [entity.entity_id, entity]));
  if (byId.size !== entityValues.length) {
    issues.push(issue("id_duplicate", "/entities", "entity IDs must be unique"));
  }
  for (const kind of ["solid", "face", "edge", "vertex"]) {
    const actual = new Set(
      [...byId.entries()]
        .filter(([entityId, entity]) => entity.kind === kind && typeof entityId === "string")
        .map(([entityId]) => entityId),
    );
    const expected = new Set([...actual].map((_id, index) => `entity/${kind}/${index}`));
    if (!setsEqual(actual, expected)) {
      issues.push(issue("entity_topology_invalid", "/entities", `${kind} entity IDs must use dense zero-based ordinals`));
    }
  }
  const kindGeometry: Record<string, Set<unknown>> = {
    solid: new Set(["brep_solid"]),
    face: new Set(["plane", "cylinder", "cone", "sphere", "torus", "bspline_surface", "other_surface"]),
    edge: new Set(["line", "circle", "ellipse", "bspline_curve", "other_curve"]),
    vertex: new Set(["point"]),
  };
  const expectedPropertyKeys: Record<string, Set<unknown>> = {
    solid: new Set(["quality", "bounds", "volume", "surface_area", "centroid"]),
    face: new Set(["quality", "bounds", "area", "centroid", "orientation"]),
    edge: new Set(["quality", "bounds", "length", "centroid"]),
    vertex: new Set(["quality", "bounds", "position"]),
  };
  entities.forEach((entity, index) => {
    const path = `/entities/${index}`;
    const entityId = entity.entity_id;
    const kind = entity.kind;
    if (typeof entityId === "string" && !entityId.startsWith(`entity/${String(kind)}/`)) {
      issues.push(issue("entity_topology_invalid", `${path}/entity_id`, "entity ID kind differs from entity kind"));
    }
    const geometry = isRecord(entity.geometry) ? entity.geometry : {};
    if (typeof kind === "string" && !kindGeometry[kind]?.has(geometry.type)) {
      issues.push(issue("entity_topology_invalid", `${path}/geometry/type`, "geometry variant is incompatible with entity kind"));
    }
    issues.push(...analyticIssues(geometry, `${path}/geometry`));
    const properties = isRecord(entity.properties) ? entity.properties : {};
    if (typeof kind === "string" && !setsEqual(new Set(Object.keys(properties)), expectedPropertyKeys[kind] ?? new Set())) {
      issues.push(issue("entity_topology_invalid", `${path}/properties`, "property record is incompatible with entity kind"));
    }
    const parents = Array.isArray(entity.parent_entity_ids) ? entity.parent_entity_ids : [];
    const children = Array.isArray(entity.child_entity_ids) ? entity.child_entity_ids : [];
    if (
      kind === "solid" &&
      (parents.length > 0 || children.length === 0 || children.some((child) => byId.get(child)?.kind !== "face"))
    ) {
      issues.push(issue("entity_topology_invalid", path, "solid must own one or more faces and have no parent"));
    }
    if (
      kind === "face" &&
      (parents.length !== 1 || byId.get(parents[0])?.kind !== "solid" || children.length === 0 || children.some((child) => byId.get(child)?.kind !== "edge"))
    ) {
      issues.push(issue("entity_topology_invalid", path, "face must have one solid parent and one or more edge children"));
    }
    if (
      kind === "edge" &&
      (parents.length === 0 || parents.some((parent) => byId.get(parent)?.kind !== "face") ||
        (children.length !== 1 && children.length !== 2) || children.some((child) => byId.get(child)?.kind !== "vertex"))
    ) {
      issues.push(issue("entity_topology_invalid", path, "edge must have face parents and one or two vertex children"));
    }
    if (
      kind === "vertex" &&
      (parents.length === 0 || parents.some((parent) => byId.get(parent)?.kind !== "edge") || children.length > 0)
    ) {
      issues.push(issue("entity_topology_invalid", path, "vertex must have edge parents and no children"));
    }
    for (const parent of parents) {
      const target = byId.get(parent);
      if (target === undefined) issues.push(issue("reference_missing", `${path}/parent_entity_ids`, "parent entity does not exist"));
      else if (!Array.isArray(target.child_entity_ids) || !target.child_entity_ids.includes(entityId)) issues.push(issue("entity_topology_invalid", `${path}/parent_entity_ids`, "parent relation is not reciprocal"));
    }
    for (const child of children) {
      const target = byId.get(child);
      if (target === undefined) issues.push(issue("reference_missing", `${path}/child_entity_ids`, "child entity does not exist"));
      else if (!Array.isArray(target.parent_entity_ids) || !target.parent_entity_ids.includes(entityId)) issues.push(issue("entity_topology_invalid", `${path}/child_entity_ids`, "child relation is not reciprocal"));
    }
    const source = entity.source;
    if (isRecord(source) && source.kind === "model_topology") {
      const expectedTopologyKind: Record<string, string> = { solid: "SOLID", face: "FACE", edge: "EDGE", vertex: "VERTEX" };
      if (typeof kind === "string" && source.topology_kind !== expectedTopologyKind[kind]) {
        issues.push(issue("source_matrix_invalid", `${path}/source/topology_kind`, "topology source kind differs from entity kind"));
      }
    }
    const frame = entity.sdk_connector_frame;
    if (kind === "solid" && frame !== null) {
      issues.push(issue("connector_invalid", `${path}/sdk_connector_frame`, "solid connector frame must be null"));
    }
    if ((kind === "face" || kind === "vertex") && frame === null) {
      issues.push(issue("connector_invalid", `${path}/sdk_connector_frame`, "face and vertex connector frames must be present"));
    }
    if (frame !== null && frame !== undefined) {
      const frameIssue = transformIssue(frame, `${path}/sdk_connector_frame`);
      if (frameIssue !== null) issues.push(frameIssue);
    }
    const status = entity.render_status;
    if (kind !== "edge" && status !== "rendered") {
      issues.push(issue("entity_topology_invalid", `${path}/render_status`, "only edges may be degenerate"));
    }
    if (kind === "solid" && entity.connector_binding_status !== "not_applicable") {
      issues.push(issue("connector_invalid", `${path}/connector_binding_status`, "solid binding status must be not_applicable"));
    }
    if (
      kind === "edge" &&
      frame === null &&
      !new Set(["frame_undefined", "owner_not_part", "source_not_model"]).has(entity.connector_binding_status as string)
    ) {
      issues.push(issue("connector_invalid", `${path}/connector_binding_status`, "edge without frame cannot be supported"));
    }
    if (kind === "vertex") {
      const point = geometry.position;
      if (!equalJson(properties.position, point)) {
        issues.push(issue("bounds_invalid", `${path}/properties/position`, "vertex property position differs from geometry point"));
      }
      issues.push(...boundsIssues(properties.bounds, `${path}/properties/bounds`, point));
    } else {
      issues.push(...boundsIssues(properties.bounds, `${path}/properties/bounds`, properties.centroid));
    }
  });
  const faceIds = new Set([...byId.entries()].filter(([, entity]) => entity.kind === "face").map(([entityId]) => entityId));
  const renderedEdgeIds = new Set([...byId.entries()].filter(([, entity]) => entity.kind === "edge" && entity.render_status === "rendered").map(([entityId]) => entityId));
  const degenerateEdgeIds = new Set([...byId.entries()].filter(([, entity]) => entity.kind === "edge" && entity.render_status === "degenerate").map(([entityId]) => entityId));
  for (const [groupsKey, expectedIds, divisor] of [["face_groups", faceIds, 3], ["edge_groups", renderedEdgeIds, 2]] as const) {
    const groups = Array.isArray(asset[groupsKey]) ? (asset[groupsKey] as unknown[]).filter(isRecord) : [];
    const groupIds = groups.map((group) => group.entity_id);
    if (!setsEqual(new Set(groupIds), expectedIds) || new Set(groupIds).size !== groupIds.length) {
      issues.push(issue("entity_range_invalid", `/${groupsKey}`, `${groupsKey} do not map exactly one group per rendered entity`));
    }
    let first = 0;
    groups.forEach((group, index) => {
      const path = `/${groupsKey}/${index}`;
      if (group.group_id !== index || group.first_index !== first) issues.push(issue("entity_range_invalid", path, "group IDs and ranges must be continuous"));
      if (typeof group.index_count === "number") {
        if (group.index_count <= 0 || group.index_count % divisor !== 0) issues.push(issue("entity_range_invalid", `${path}/index_count`, "group count has invalid primitive cardinality"));
        first += group.index_count;
      }
    });
  }
  const edgeGroups = Array.isArray(asset.edge_groups) ? asset.edge_groups.filter(isRecord) : [];
  if (edgeGroups.some((group) => degenerateEdgeIds.has(group.entity_id))) {
    issues.push(issue("entity_range_invalid", "/edge_groups", "degenerate edges must not have render groups"));
  }
  return issues;
}

function presentationSemanticIssues(value: JsonRecord): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const appearances = Array.isArray(value.appearances) ? value.appearances.filter(isRecord) : [];
  const appearanceNames = appearances.map((appearance) => appearance.name);
  if (new Set(appearanceNames).size !== appearanceNames.length) {
    issues.push(issue("id_duplicate", "/appearances", "presentation appearance names must be unique"));
  }
  const appearanceNameSet = new Set(appearanceNames);
  const overrides = Array.isArray(value.node_overrides) ? value.node_overrides.filter(isRecord) : [];
  const nodeIds = overrides.map((override) => override.node_id);
  if (new Set(nodeIds).size !== nodeIds.length) {
    issues.push(issue("id_duplicate", "/node_overrides", "node overrides must target unique node IDs"));
  }
  overrides.forEach((override, index) => {
    if (override.appearance_name !== undefined && !appearanceNameSet.has(override.appearance_name)) {
      issues.push(issue("presentation_reference_invalid", `/node_overrides/${index}/appearance_name`, "appearance_name does not exist"));
    }
  });
  const cameras = Array.isArray(value.cameras) ? value.cameras.filter(isRecord) : [];
  const cameraNames = cameras.map((camera) => camera.name);
  if (new Set(cameraNames).size !== cameraNames.length) {
    issues.push(issue("id_duplicate", "/cameras", "presentation camera names must be unique"));
  }
  cameras.forEach((camera, index) => {
    if (typeof camera.near === "number" && typeof camera.far === "number" && camera.far <= camera.near) {
      issues.push(issue("bounds_invalid", `/cameras/${index}/far`, "camera far must exceed near"));
    }
    const transform = transformIssue(camera.transform, `/cameras/${index}/transform`);
    if (transform !== null) issues.push(transform);
  });
  return issues;
}

function connectorBindingSemanticIssues(value: JsonRecord): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const sourceModel = isRecord(value.source_model) ? value.source_model : {};
  const target = isRecord(value.target) ? value.target : {};
  const expectedSource = isRecord(target.expected_source) ? target.expected_source : {};
  if (sourceModel.graph_id !== expectedSource.graph_id) {
    issues.push(issue("source_matrix_invalid", "/target/expected_source/graph_id", "target graph differs from source model graph"));
  }
  if (typeof target.entity_id === "string" && target.entity_id.startsWith("entity/vertex/") && target.flip !== false) {
    issues.push(issue("connector_invalid", "/target/flip", "vertex connector target requires flip=false"));
  }
  return issues;
}

function normalizedProductSemanticIssues(value: JsonRecord): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  const connectors = Array.isArray(value.connectors) ? value.connectors.filter(isRecord) : [];
  const connectorIds = connectors.map((connector) => connector.connector_id);
  if (new Set(connectorIds).size !== connectorIds.length) {
    issues.push(issue("id_duplicate", "/connectors", "connector IDs must be unique"));
  }
  if (value.kind !== "assembly") return issues;

  const components = Array.isArray(value.components) ? value.components.filter(isRecord) : [];
  const componentIds = components.map((component) => component.component_id);
  if (new Set(componentIds).size !== componentIds.length) {
    issues.push(issue("id_duplicate", "/components", "component IDs must be unique"));
  }
  const componentSet = new Set(componentIds);
  const grounded = Array.isArray(value.grounded_component_ids) ? value.grounded_component_ids : [];
  if (grounded.some((componentId) => !componentSet.has(componentId))) {
    issues.push(issue("reference_missing", "/grounded_component_ids", "grounded component does not exist"));
  }
  const constraints = Array.isArray(value.constraints) ? value.constraints.filter(isRecord) : [];
  const constraintIds = constraints.map((constraint) => constraint.constraint_id);
  if (new Set(constraintIds).size !== constraintIds.length) {
    issues.push(issue("id_duplicate", "/constraints", "constraint IDs must be unique"));
  }
  constraints.forEach((constraint, index) => {
    for (const referenceKey of ["connector_a", "connector_b"]) {
      const reference = constraint[referenceKey];
      if (isRecord(reference) && !componentSet.has(reference.component_id)) {
        issues.push(issue("reference_missing", `/constraints/${index}/${referenceKey}/component_id`, "constraint component does not exist"));
      }
    }
    for (const limitKey of ["distance_limit", "angle_limit"]) {
      const limit = constraint[limitKey];
      if (
        isRecord(limit) &&
        typeof limit.lower_value === "number" &&
        typeof limit.upper_value === "number" &&
        limit.lower_value > limit.upper_value
      ) {
        issues.push(issue("bounds_invalid", `/constraints/${index}/${limitKey}`, "constraint lower limit exceeds upper limit"));
      }
    }
  });
  return issues;
}

function validateDocument(
  value: unknown,
  artifact: DocumentArtifact,
  validator: ValidateFunction,
  semanticIssues: (parsed: JsonRecord) => ValidationIssue[],
  checkArrayOrder = false,
  limits: SceneResourceLimits = BASE_LIMITS,
): ValidationReport {
  const serializedInput = typeof value === "string" || value instanceof Uint8Array;
  const parsed = parseInput(value, serializedInput);
  if (parsed.value === undefined && parsed.issues.length > 0) return report(parsed.issues, artifact);
  const issues = [
    ...serializedSizeIssues(value, artifact, limits),
    ...parsed.issues,
    ...jsonResourceIssues(parsed.value, limits),
    ...resourceCountIssues(parsed.value, artifact, limits),
  ];
  if (issues.some((item) => item.code === "resource_limit_exceeded" && item.message.includes("nesting"))) {
    return report(issues, artifact);
  }
  issues.push(...structuralIssues(parsed.value, validator));
  if (isRecord(parsed.value) && !issues.some((item) => item.phase === "parse" || item.phase === "structure")) {
    if (checkArrayOrder) issues.push(...arrayOrderIssues(parsed.value));
    issues.push(...semanticIssues(parsed.value));
  }
  return report(issues, artifact);
}

export function validateSceneManifest(value: unknown, limits: SceneResourceLimits = BASE_LIMITS): ValidationReport {
  return validateDocument(value, "scene", validateSceneSchema, sceneSemanticIssues, true, limits);
}

export function validateEntityAsset(value: unknown, limits: SceneResourceLimits = BASE_LIMITS): ValidationReport {
  return validateDocument(value, "entities", validateEntitiesSchema, entitySemanticIssues, true, limits);
}

export function validatePresentation(value: unknown, limits: SceneResourceLimits = BASE_LIMITS): ValidationReport {
  return validateDocument(value, "presentation", validatePresentationSchema, presentationSemanticIssues, false, limits);
}

export function validateConnectorBinding(value: unknown, limits: SceneResourceLimits = BASE_LIMITS): ValidationReport {
  return validateDocument(value, "connector_binding", validateConnectorBindingSchema, connectorBindingSemanticIssues, false, limits);
}

export function validateNormalizedProduct(value: unknown, limits: SceneResourceLimits = BASE_LIMITS): ValidationReport {
  return validateDocument(value, "normalized_product", validateNormalizedProductSchema, normalizedProductSemanticIssues, false, limits);
}

type PackageMediaRole = "geometry" | "edge" | "entity" | "model_source" | "imported_source" | "python_source" | "presentation";

interface PackageRecord extends JsonRecord {
  byte_length: unknown;
  content_hash: unknown;
  media_role: PackageMediaRole;
}

function packageRecords(scene: JsonRecord): { records: Map<string, PackageRecord>; issues: ValidationIssue[] } {
  const result = new Map<string, PackageRecord>();
  const issues: ValidationIssue[] = [];
  const add = (uri: unknown, byteLength: unknown, contentHash: unknown, mediaRole: PackageMediaRole): void => {
    if (typeof uri !== "string") return;
    const record: PackageRecord = { byte_length: byteLength, content_hash: contentHash, media_role: mediaRole };
    const previous = result.get(uri);
    if (
      previous !== undefined &&
      (previous.byte_length !== record.byte_length ||
        previous.content_hash !== record.content_hash ||
        previous.media_role !== record.media_role)
    ) {
      issues.push(issue("package_member_set_invalid", "", "manifest records for one URI disagree on hash, length, or media role", "package"));
      return;
    }
    result.set(uri, record);
  };
  for (const [key, mediaRole] of [["geometry_assets", "geometry"], ["edge_assets", "edge"], ["entity_assets", "entity"]] as const) {
    const records = Array.isArray(scene[key]) ? scene[key] : [];
    for (const value of records) if (isRecord(value)) add(value.uri, value.byte_length, value.content_hash, mediaRole);
  }
  if (isRecord(scene.source) && typeof scene.source.embedded_artifact_uri === "string") {
    add(
      scene.source.embedded_artifact_uri,
      scene.source.embedded_artifact_byte_length,
      scene.source.artifact_hash,
      scene.source.kind === "model" ? "model_source" : "imported_source",
    );
    const sourceFiles = Array.isArray(scene.source.source_files) ? scene.source.source_files : [];
    for (const sourceFile of sourceFiles) {
      if (isRecord(sourceFile)) add(sourceFile.uri, sourceFile.byte_length, sourceFile.content_hash, "python_source");
    }
  }
  if (isRecord(scene.presentation_source) && typeof scene.presentation_source.embedded_artifact_uri === "string") {
    add(
      scene.presentation_source.embedded_artifact_uri,
      scene.presentation_source.embedded_artifact_byte_length,
      scene.presentation_source.artifact_hash,
      "presentation",
    );
  }
  return { records: result, issues };
}

export interface PackageBudgetContributions {
  sceneJsonBytes: number;
  glbDecodedBufferBytes: number;
  entityJsonBytes: number;
  otherImmutableJsonBytes: number;
  entityCount: number;
  entityVertexCount: number;
  triangleVertexCount: number;
  triangleCount: number;
  lineVertexCount: number;
  lineSegmentCount: number;
}

export interface PackageBudgetTotals {
  staticDecodedBufferBytes: number;
  entityCount: number;
  triangleVertexTotal: number;
  triangleTotal: number;
  lineVertexTotal: number;
  lineSegmentTotal: number;
}

export interface PackageBudgetLimits {
  static_decoded_buffer_bytes: number;
  entities_total: number;
  triangle_vertices_total: number;
  triangles_total: number;
  line_vertices_total: number;
  line_segments_total: number;
}

export function computePackageBudgetTotals(input: PackageBudgetContributions): PackageBudgetTotals {
  return {
    staticDecodedBufferBytes:
      input.sceneJsonBytes +
      input.glbDecodedBufferBytes +
      input.entityJsonBytes +
      input.otherImmutableJsonBytes +
      2 * input.entityVertexCount * 16,
    entityCount: input.entityCount,
    triangleVertexTotal: input.triangleVertexCount,
    triangleTotal: input.triangleCount,
    lineVertexTotal: input.lineVertexCount,
    lineSegmentTotal: input.lineSegmentCount,
  };
}

export function packageBudgetIssues(
  totals: PackageBudgetTotals,
  limits: PackageBudgetLimits = BASE_LIMITS,
): ValidationIssue[] {
  const issues: ValidationIssue[] = [];
  if (totals.staticDecodedBufferBytes > limits.static_decoded_buffer_bytes) {
    issues.push(issue("static_buffer_limit_exceeded", "", "static decoded buffer formula exceeds resource limit", "budget"));
  }
  if (totals.entityCount > limits.entities_total) {
    issues.push(issue("resource_limit_exceeded", "/entity_assets", "total entity count exceeds resource limit", "budget"));
  }
  for (const [total, limit, message] of [
    [totals.triangleVertexTotal, limits.triangle_vertices_total, "total triangle GLB vertex count exceeds resource limit"],
    [totals.triangleTotal, limits.triangles_total, "total triangle count exceeds resource limit"],
    [totals.lineVertexTotal, limits.line_vertices_total, "total line GLB vertex count exceeds resource limit"],
    [totals.lineSegmentTotal, limits.line_segments_total, "total line segment count exceeds resource limit"],
  ] as const) {
    if (total > limit) issues.push(issue("resource_limit_exceeded", "", message, "budget"));
  }
  return issues;
}


const sourceDecoder = new TextDecoder("utf-8", { fatal: true });

function sourceSegment(
  content: string,
  line: number,
  column: number,
  endLine: number,
  endColumn: number,
): string | null {
  const normalized = content.replace(/\r\n?/g, "\n");
  const lines = normalized.split("\n");
  if (normalized.endsWith("\n")) lines.pop();
  if (lines.length === 0 || line < 1 || endLine < line || endLine > lines.length) return null;
  const startText = Array.from(lines[line - 1]);
  const endText = Array.from(lines[endLine - 1]);
  if (column < 0 || endColumn < 0 || column > startText.length || endColumn > endText.length || (line === endLine && endColumn < column)) return null;
  if (line === endLine) return startText.slice(column, endColumn).join("");
  const parts = [startText.slice(column).join("")];
  for (let index = line; index < endLine - 1; index += 1) parts.push(lines[index]);
  parts.push(endText.slice(0, endColumn).join(""));
  return parts.join("\n");
}

function expectedCallsiteId(source: JsonRecord): string {
  const material = [
    source.path ?? "",
    source.line,
    source.column,
    source.end_line,
    source.end_column,
    source.call_text,
  ].map(String).join("\x1f");
  return `callsite_${sha256(Buffer.from(material, "utf8")).slice("sha256:".length, "sha256:".length + 16)}`;
}

function operationSourceIssues(
  source: unknown,
  path: string,
  sourceFiles: ReadonlyMap<string, string>,
): ValidationIssue[] {
  if (!isRecord(source)) return [issue("source_matrix_invalid", path, "operation source must be an object")];
  const issues: ValidationIssue[] = [];
  const keys = Object.keys(source);
  if (keys.length !== operationSourceKeys.size || keys.some((key) => !operationSourceKeys.has(key))) {
    issues.push(issue("source_matrix_invalid", path, "operation source fields do not match source mapping schema 1.0"));
  }
  const line = source.line;
  const column = source.column;
  const endLine = source.end_line;
  const endColumn = source.end_column;
  const assignmentTargets = source.assignment_targets;
  const valid =
    source.schema_version === "1.0" &&
    (source.path_kind === "project_relative" || source.path_kind === "unresolved") &&
    Number.isSafeInteger(line) && (line as number) >= 1 &&
    Number.isSafeInteger(column) && (column as number) >= 0 &&
    Number.isSafeInteger(endLine) && (endLine as number) >= (line as number) &&
    Number.isSafeInteger(endColumn) && (endColumn as number) >= 0 &&
    typeof source.call_text === "string" &&
    typeof source.callsite_id === "string" && /^callsite_[0-9a-f]{16}$/.test(source.callsite_id) &&
    Array.isArray(assignmentTargets) && assignmentTargets.every((value) => typeof value === "string" && value.length > 0);
  if (!valid) {
    issues.push(issue("source_matrix_invalid", path, "operation source values do not match source mapping schema 1.0"));
    return issues;
  }
  if (source.path_kind === "unresolved") {
    if (source.path !== null) issues.push(issue("source_matrix_invalid", `${path}/path`, "unresolved operation source path must be null"));
  } else if (typeof source.path !== "string" || !sourceFiles.has(source.path)) {
    issues.push(issue("source_matrix_invalid", `${path}/path`, "operation source path does not resolve to an embedded source file"));
  } else {
    const segment = sourceSegment(sourceFiles.get(source.path)!, line as number, column as number, endLine as number, endColumn as number);
    if (segment === null || segment !== source.call_text) {
      issues.push(issue("source_matrix_invalid", path, "operation source span does not match embedded source text"));
    }
  }
  if (source.callsite_id !== expectedCallsiteId(source)) {
    issues.push(issue("source_matrix_invalid", `${path}/callsite_id`, "operation callsite_id does not match its canonical source span"));
  }
  return issues;
}

function embeddedModelIssues(
  scene: JsonRecord,
  payload: Buffer,
  sourceFiles: ReadonlyMap<string, string>,
  entityPayloads: ReadonlyMap<string, JsonRecord>,
): ValidationIssue[] {
  const prefix = "/model/model.json";
  let modelValue: unknown;
  try {
    modelValue = parseStrictJson(payload);
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    if (error instanceof DuplicateKeyError) return [issue("duplicate_json_key", "", message, "parse")];
    if (error instanceof TypeError && message.toLowerCase().includes("utf")) return [issue("invalid_utf8", prefix, message, "parse")];
    return [issue("schema_invalid", prefix, message, "structure")];
  }
  if (!isRecord(modelValue)) return [issue("schema_invalid", prefix, "embedded model must be a JSON object", "structure")];
  const model = modelValue;
  if (model.schema_version !== "2.0" || !isRecord(model.graph)) {
    return [issue("schema_invalid", prefix, "embedded model does not contain a schema 2.0 graph", "structure")];
  }
  const graph = model.graph;
  const sceneSource = isRecord(scene.source) ? scene.source : {};
  if (graph.graph_id !== sceneSource.graph_id) {
    return [issue("source_matrix_invalid", `${prefix}/graph/graph_id`, "embedded model graph_id differs from scene source")];
  }
  if (!Array.isArray(graph.nodes)) {
    return [issue("schema_invalid", `${prefix}/graph/nodes`, "embedded model graph nodes must be an array", "structure")];
  }

  const issues: ValidationIssue[] = [];
  const nodeMap = new Map<string, JsonRecord>();
  const nodeIndexes = new Map<string, number>();
  graph.nodes.forEach((nodeValue, index) => {
    const nodePath = `${prefix}/graph/nodes/${index}`;
    if (!isRecord(nodeValue)) {
      issues.push(issue("schema_invalid", nodePath, "model graph node must be an object", "structure"));
      return;
    }
    const node = nodeValue;
    const validNode =
      typeof node.node_id === "string" && node.node_id.length > 0 &&
      typeof node.op === "string" &&
      isRecord(node.params) &&
      Array.isArray(node.inputs) && node.inputs.every((value) => typeof value === "string") &&
      Number.isSafeInteger(node.output_count) && (node.output_count as number) >= 1;
    if (!validNode) {
      issues.push(issue("schema_invalid", nodePath, "model graph node has an invalid Viewer operation shape", "structure"));
      return;
    }
    const nodeId = node.node_id as string;
    if (nodeMap.has(nodeId)) {
      issues.push(issue("id_duplicate", `${nodePath}/node_id`, "model graph node_id is duplicated"));
      return;
    }
    nodeMap.set(nodeId, node);
    nodeIndexes.set(nodeId, index);
    if (Object.hasOwn(node, "source")) issues.push(...operationSourceIssues(node.source, `${nodePath}/source`, sourceFiles));
  });
  for (const [nodeId, node] of nodeMap) {
    for (const inputId of node.inputs as string[]) {
      if (!nodeMap.has(inputId)) issues.push(issue("reference_missing", `${prefix}/graph/nodes/${nodeIndexes.get(nodeId)!}/inputs`, "model graph input references a missing node"));
    }
  }
  if (!Array.isArray(model.leaf_ids) || !model.leaf_ids.every((value) => typeof value === "string" && nodeMap.has(value))) {
    issues.push(issue("reference_missing", `${prefix}/leaf_ids`, "model leaf_ids must resolve to graph nodes"));
  }

  const validateReference = (value: unknown, path: string): void => {
    if (!isRecord(value)) return;
    const node = typeof value.node_id === "string" ? nodeMap.get(value.node_id) : undefined;
    if (node === undefined || !Number.isSafeInteger(value.output_slot) || (value.output_slot as number) < 0 || (value.output_slot as number) >= (node.output_count as number)) {
      issues.push(issue("reference_missing", path, "model source does not resolve to an embedded graph output"));
    }
  };
  (Array.isArray(scene.definitions) ? scene.definitions : []).forEach((definitionValue, index) => {
    if (!isRecord(definitionValue) || !isRecord(definitionValue.source)) return;
    if (definitionValue.source.kind === "product_model" || definitionValue.source.kind === "model_output") validateReference(definitionValue.source, `/definitions/${index}/source`);
  });
  (Array.isArray(scene.connectors) ? scene.connectors : []).forEach((connectorValue, index) => {
    if (isRecord(connectorValue) && isRecord(connectorValue.source) && connectorValue.source.kind === "model_operation") validateReference(connectorValue.source, `/connectors/${index}/source`);
  });
  for (const [uri, entityPayload] of entityPayloads) {
    (Array.isArray(entityPayload.entities) ? entityPayload.entities : []).forEach((entityValue, index) => {
      if (!isRecord(entityValue) || !isRecord(entityValue.source)) return;
      if (entityValue.source.kind === "model_output" || entityValue.source.kind === "model_topology") validateReference(entityValue.source, `/${uri}/entities/${index}/source`);
    });
  }
  return issues;
}

function embeddedPresentationIssues(
  scene: JsonRecord,
  payload: Buffer,
  uri: string,
  limits: SceneResourceLimits,
): ValidationIssue[] {
  const prefix = `/${uri}`;
  const presentationReport = validatePresentation(payload, limits);
  const issues = presentationReport.issues.map((item) => {
    const code = item.code === "presentation_reference_invalid" ? "source_matrix_invalid" : item.code;
    const path = hasRootPointerPolicy(code) ? "" : `${prefix}${item.path}`;
    return issue(code, path, item.message, item.phase);
  });
  if (presentationReport.issues.some((item) => item.phase === "parse" || item.phase === "structure")) return issues;
  let parsed: unknown;
  try { parsed = parseCanonicalJson(payload); } catch { return issues; }
  if (!isRecord(parsed) || !isRecord(scene.presentation_source)) return issues;
  const presentation = parsed;
  const presentationSource = scene.presentation_source;
  if (presentation.presentation_id !== presentationSource.presentation_id) {
    issues.push(issue("source_matrix_invalid", `${prefix}/presentation_id`, "presentation_id differs from manifest presentation_source"));
  }
  if (presentation.source_scene_id !== scene.scene_id) {
    issues.push(issue("source_matrix_invalid", `${prefix}/source_scene_id`, "presentation source_scene_id differs from manifest scene_id"));
  }

  const sceneAppearances = (Array.isArray(scene.appearances) ? scene.appearances : []).filter(isRecord);
  const expectedAppearanceIds = new Map<unknown, string>();
  const authoredAppearances = (Array.isArray(presentation.appearances) ? presentation.appearances : []).filter(isRecord);
  authoredAppearances.forEach((authored, index) => {
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
        presentation_id: presentation.presentation_id,
      },
    };
    const appearanceId = `appearance/evaluated/${sha256(canonicalJsonBytes(evaluated)).slice("sha256:".length)}`;
    expectedAppearanceIds.set(authored.name, appearanceId);
    const expected = { appearance_id: appearanceId, ...evaluated };
    if (sceneAppearances.filter((appearance) => equalJson(appearance, expected)).length !== 1) {
      issues.push(issue("source_matrix_invalid", `${prefix}/appearances/${index}`, "presentation appearance does not resolve to exactly one evaluated scene appearance"));
    }
  });
  const expectedAppearanceIdSet = new Set(expectedAppearanceIds.values());
  sceneAppearances.forEach((appearance, index) => {
    if (
      isRecord(appearance.source) &&
      appearance.source.kind === "presentation" &&
      !expectedAppearanceIdSet.has(appearance.appearance_id as string)
    ) {
      issues.push(issue("source_matrix_invalid", `/appearances/${index}/source/appearance_name`, "evaluated presentation appearance does not resolve to an authored appearance"));
    }
  });

  const sceneNodes = (Array.isArray(scene.nodes) ? scene.nodes : []).filter(isRecord);
  const nodeMap = new Map<unknown, JsonRecord>(sceneNodes.map((node) => [node.node_id, node]));
  const definitionMap = new Map<unknown, JsonRecord>(
    (Array.isArray(scene.definitions) ? scene.definitions : []).filter(isRecord).map((definition) => [definition.definition_id, definition]),
  );
  const overrides = (Array.isArray(presentation.node_overrides) ? presentation.node_overrides : []).filter(isRecord);
  const overrideMap = new Map<unknown, JsonRecord>(overrides.map((override) => [override.node_id, override]));
  overrides.forEach((override, index) => {
    const node = nodeMap.get(override.node_id);
    if (node === undefined) {
      issues.push(issue("source_matrix_invalid", `${prefix}/node_overrides/${index}/node_id`, "node override target does not exist in the scene"));
      return;
    }
    if (override.appearance_name !== undefined) {
      const definition = definitionMap.get(node.definition_id);
      if (definition === undefined || (definition.kind !== "part" && definition.kind !== "shape")) {
        issues.push(issue("source_matrix_invalid", `${prefix}/node_overrides/${index}/appearance_name`, "appearance override target is not a renderable Part or Shape"));
      }
    }
  });
  sceneNodes.forEach((node, index) => {
    const override = overrideMap.get(node.node_id);
    const expectedVisible = override?.visible ?? true;
    const appearanceName = override?.appearance_name;
    const expectedAppearanceId = appearanceName === undefined ? undefined : expectedAppearanceIds.get(appearanceName);
    if (node.visible !== expectedVisible) {
      issues.push(issue("source_matrix_invalid", `/nodes/${index}/visible`, "node visibility does not match the embedded presentation"));
    }
    if (expectedAppearanceId !== undefined && node.appearance_override_id !== expectedAppearanceId) {
      issues.push(issue("source_matrix_invalid", `/nodes/${index}/appearance_override_id`, "node appearance override does not resolve the embedded presentation name"));
    }
    if (appearanceName === undefined && node.appearance_override_id !== null) {
      issues.push(issue("source_matrix_invalid", `/nodes/${index}/appearance_override_id`, "node appearance override is not authored by the embedded presentation"));
    }
  });

  const sceneCameras = (Array.isArray(scene.cameras) ? scene.cameras : []).filter(isRecord);
  const expectedCameraIds = new Set<string>();
  const authoredCameras = (Array.isArray(presentation.cameras) ? presentation.cameras : []).filter(isRecord);
  authoredCameras.forEach((authored, index) => {
    if (authored.parent_node_id !== null && !nodeMap.has(authored.parent_node_id)) {
      issues.push(issue("source_matrix_invalid", `${prefix}/cameras/${index}/parent_node_id`, "presentation camera parent does not exist in the scene"));
    }
    const cameraId = `camera/${String(presentation.presentation_id)}/${encodeSegment(String(authored.name ?? ""))}`;
    expectedCameraIds.add(cameraId);
    const expected = { camera_id: cameraId, ...authored };
    if (sceneCameras.filter((camera) => equalJson(camera, expected)).length !== 1) {
      issues.push(issue("source_matrix_invalid", `${prefix}/cameras/${index}`, "presentation camera does not resolve to exactly one evaluated scene camera"));
    }
  });
  sceneCameras.forEach((camera, index) => {
    if (!expectedCameraIds.has(camera.camera_id as string)) {
      issues.push(issue("source_matrix_invalid", `/cameras/${index}`, "evaluated scene camera is not authored by the embedded presentation"));
    }
  });
  return issues;
}

function transformedBounds(info: GlbInfo, matrix: unknown): JsonRecord | null {
  if (!Array.isArray(matrix) || matrix.length !== 16 || !matrix.every((item) => typeof item === "number")) return null;
  const [minimum, maximum] = info.positionBounds;
  const points: number[][] = [];
  for (const x of [minimum[0], maximum[0]]) for (const y of [minimum[1], maximum[1]]) for (const z of [minimum[2], maximum[2]]) {
    points.push([matrix[0] * x + matrix[1] * y + matrix[2] * z + matrix[3], matrix[4] * x + matrix[5] * y + matrix[6] * z + matrix[7], matrix[8] * x + matrix[9] * y + matrix[10] * z + matrix[11]]);
  }
  return { min: [0, 1, 2].map((axis) => Math.min(...points.map((point) => point[axis]))), max: [0, 1, 2].map((axis) => Math.max(...points.map((point) => point[axis]))) };
}

function equalJson(left: unknown, right: unknown): boolean {
  return Buffer.compare(canonicalJsonBytes(left), canonicalJsonBytes(right)) === 0;
}

export function validateScenePackage(
  sceneInput: unknown,
  blobsInput: ReadonlyMap<string, Uint8Array> | Record<string, Uint8Array>,
  limits: SceneResourceLimits = BASE_LIMITS,
): ValidationReport {
  const manifest = validateSceneManifest(sceneInput, limits);
  const issues = [...manifest.issues];
  const parsed = parseInput(sceneInput, typeof sceneInput === "string" || sceneInput instanceof Uint8Array);
  if (!isRecord(parsed.value) || issues.some((item) => item.phase === "parse" || item.phase === "structure")) return report(issues, "package");
  const scene = parsed.value;
  const blobs = blobsInput instanceof Map ? new Map(blobsInput) : new Map(Object.entries(blobsInput));
  const packageRecordResult = packageRecords(scene);
  const records = packageRecordResult.records;
  issues.push(...packageRecordResult.issues);
  if (blobs.size !== records.size || [...blobs.keys()].some((name) => !records.has(name))) issues.push(issue("package_member_set_invalid", "", "blob keys do not exactly equal manifest URI references", "package"));
  const glbs = new Map<string, GlbInfo>();
  const entities = new Map<string, JsonRecord>();
  let embeddedModel: Buffer | null = null;
  const sourceFiles = new Map<string, string>();
  const sourcePathByUri = new Map<string, string>();
  if (isRecord(scene.source) && Array.isArray(scene.source.source_files)) {
    for (const sourceFile of scene.source.source_files) {
      if (isRecord(sourceFile) && typeof sourceFile.uri === "string" && typeof sourceFile.path === "string") {
        sourcePathByUri.set(sourceFile.uri, sourceFile.path);
      }
    }
  }
  const budget: PackageBudgetContributions = {
    sceneJsonBytes: canonicalJsonBytes(scene).length,
    glbDecodedBufferBytes: 0,
    entityJsonBytes: 0,
    otherImmutableJsonBytes: 0,
    entityCount: 0,
    entityVertexCount: 0,
    triangleVertexCount: 0,
    triangleCount: 0,
    lineVertexCount: 0,
    lineSegmentCount: 0,
  };
  for (const [uri, asset] of records) {
    const value = blobs.get(uri);
    if (value === undefined) continue;
    const roleLimit = asset.media_role === "entity"
      ? limits.entity_json_bytes
      : asset.media_role === "model_source"
        ? limits.model_json_bytes
        : asset.media_role === "presentation"
          ? limits.presentation_json_bytes
          : limits.one_member_bytes;
    if (value.byteLength > Math.min(limits.one_member_bytes, roleLimit)) {
      issues.push(issue("resource_limit_exceeded", `/${uri}`, "package member bytes exceed resource limit", "budget"));
      continue;
    }
    const payload = Buffer.from(value);
    if (payload.length !== asset.byte_length) issues.push(issue("blob_length_mismatch", `/${uri}`, "blob length differs from manifest", "package"));
    if (sha256(payload) !== asset.content_hash) issues.push(issue("blob_hash_mismatch", `/${uri}`, "blob hash differs from manifest", "package"));
    if (asset.media_role === "geometry" || asset.media_role === "edge") {
      try {
        const info = preflightGlb(payload, asset.media_role === "geometry" ? "triangle" : "line", limits);
        glbs.set(uri, info);
        budget.glbDecodedBufferBytes += info.decodedBufferBytes;
        if (info.kind === "triangle") {
          budget.triangleVertexCount += info.vertexCount;
          budget.triangleCount += info.primitiveCount;
        } else {
          budget.lineVertexCount += info.vertexCount;
          budget.lineSegmentCount += info.primitiveCount;
        }
      }
      catch (error) { issues.push(issue("glb_profile_invalid", `/${uri}`, error instanceof Error ? error.message : String(error), "package")); }
    } else if (asset.media_role === "entity") {
      const entityReport = validateEntityAsset(payload, limits);
      for (const item of entityReport.issues) {
        issues.push(issue(
          item.code,
          hasRootPointerPolicy(item.code) ? "" : `/${uri}${item.path}`,
          item.message,
          item.phase,
        ));
      }
      try {
        const value = parseCanonicalJson(payload);
        if (isRecord(value)) {
          entities.set(uri, value);
          budget.entityJsonBytes += payload.length;
          const sidecarEntities = Array.isArray(value.entities) ? value.entities : [];
          budget.entityCount += sidecarEntities.length;
          budget.entityVertexCount += sidecarEntities.filter((entity) => isRecord(entity) && entity.kind === "vertex").length;
        }
      } catch { /* Reported above. */ }
    } else if (asset.media_role === "presentation") {
      issues.push(...embeddedPresentationIssues(scene, payload, uri, limits));
      budget.otherImmutableJsonBytes += payload.length;
    } else if (asset.media_role === "model_source") {
      embeddedModel = payload;
      budget.otherImmutableJsonBytes += payload.length;
    } else if (asset.media_role === "python_source") {
      try {
        const sourcePath = sourcePathByUri.get(uri);
        if (sourcePath !== undefined) sourceFiles.set(sourcePath, sourceDecoder.decode(payload));
      } catch (error) {
        issues.push(issue("invalid_utf8", `/${uri}`, error instanceof Error ? error.message : String(error), "parse"));
      }
      budget.otherImmutableJsonBytes += payload.length;
    }
  }
  if (embeddedModel !== null) issues.push(...embeddedModelIssues(scene, embeddedModel, sourceFiles, entities));
  issues.push(...packageBudgetIssues(computePackageBudgetTotals(budget), limits));
  const geometryById = new Map((Array.isArray(scene.geometry_assets) ? scene.geometry_assets : []).filter(isRecord).map((item) => [item.asset_id, item]));
  const edgesById = new Map((Array.isArray(scene.edge_assets) ? scene.edge_assets : []).filter(isRecord).map((item) => [item.asset_id, item]));
  const entityById = new Map((Array.isArray(scene.entity_assets) ? scene.entity_assets : []).filter(isRecord).map((item) => [item.entity_asset_id, item]));
  const definitions = Array.isArray(scene.definitions) ? scene.definitions : [];
  definitions.forEach((value, definitionIndex) => {
    if (!isRecord(value) || value.kind === "assembly") return;
    const entityRecord = entityById.get(value.entity_asset_id);
    const geometryRecord = geometryById.get(value.geometry_asset_id);
    const edgeRecord = edgesById.get(value.edge_asset_id);
    for (const [record, expectedKind] of [[geometryRecord, "geometry"], [edgeRecord, "edge"]] as const) {
      if (!isRecord(record) || typeof record.uri !== "string") continue;
      const info = glbs.get(record.uri);
      if (info !== undefined) {
        const expected = transformedBounds(info, record.asset_to_scene);
        if (expected === null || !equalJson(record.scene_local_bounds, expected)) issues.push(issue("bounds_invalid", `/definitions/${definitionIndex}`, `${expectedKind} asset scene_local_bounds differ from transformed GLB bounds`));
      }
    }
    if (!isRecord(entityRecord) || typeof entityRecord.uri !== "string") return;
    const payload = entities.get(entityRecord.uri);
    if (payload === undefined) return;
    if (payload.definition_id !== value.definition_id || payload.geometry_asset_id !== value.geometry_asset_id || payload.edge_asset_id !== value.edge_asset_id) issues.push(issue("reference_missing", `/definitions/${definitionIndex}/entity_asset_id`, "entity sidecar ownership triple differs from definition"));
    if (
      !isRecord(payload.geometry_engine) ||
      !isRecord(scene.generator) ||
      payload.geometry_engine.version !== scene.generator.ocp_version
    ) {
      issues.push(issue("source_matrix_invalid", `/definitions/${definitionIndex}/entity_asset_id`, "entity geometry engine version differs from manifest generator"));
    }
    const sceneSourceKind = isRecord(scene.source) ? scene.source.kind : undefined;
    const allowedEntitySources: Record<string, Set<string>> = {
      model: new Set(["model_output", "model_topology"]),
      imported: new Set(["imported_primitive", "unbound"]),
      manual: new Set(["unbound"]),
    };
    const definitionSource = isRecord(value.source) ? value.source : {};
    const sidecarEntities = Array.isArray(payload.entities) ? payload.entities : [];
    sidecarEntities.forEach((entityValue, entityIndex) => {
      if (!isRecord(entityValue)) return;
      const entityPath = `/${entityRecord.uri}/entities/${entityIndex}`;
      const entitySource = isRecord(entityValue.source) ? entityValue.source : null;
      if (
        entitySource === null ||
        typeof entitySource.kind !== "string" ||
        typeof sceneSourceKind !== "string" ||
        !allowedEntitySources[sceneSourceKind]?.has(entitySource.kind)
      ) {
        issues.push(issue("source_matrix_invalid", `${entityPath}/source`, "entity source is incompatible with scene source"));
      } else if (
        sceneSourceKind === "model" &&
        ["graph_id", "node_id", "output_slot"].some(
          (field) => entitySource[field] !== definitionSource[field],
        )
      ) {
        issues.push(issue("source_matrix_invalid", `${entityPath}/source`, "entity model source differs from owning definition output"));
      }

      let expectedStatus: string | null = null;
      if (entityValue.kind === "solid") expectedStatus = "not_applicable";
      else if (value.kind !== "part") expectedStatus = "owner_not_part";
      else if (sceneSourceKind !== "model") expectedStatus = "source_not_model";
      else if (entityValue.sdk_connector_frame === null) expectedStatus = "frame_undefined";
      if (expectedStatus !== null && entityValue.connector_binding_status !== expectedStatus) {
        issues.push(issue("connector_invalid", `${entityPath}/connector_binding_status`, `connector binding status must be ${expectedStatus}`));
      }
    });
    const faceTotal = (Array.isArray(payload.face_groups) ? payload.face_groups : []).filter(isRecord).reduce((sum, group) => sum + (typeof group.index_count === "number" ? group.index_count : 0), 0);
    const edgeTotal = (Array.isArray(payload.edge_groups) ? payload.edge_groups : []).filter(isRecord).reduce((sum, group) => sum + (typeof group.index_count === "number" ? group.index_count : 0), 0);
    const geometryInfo = isRecord(geometryRecord) && typeof geometryRecord.uri === "string" ? glbs.get(geometryRecord.uri) : undefined;
    const edgeInfo = isRecord(edgeRecord) && typeof edgeRecord.uri === "string" ? glbs.get(edgeRecord.uri) : undefined;
    if (geometryInfo !== undefined && faceTotal !== geometryInfo.indexCount) issues.push(issue("entity_range_invalid", `/definitions/${definitionIndex}/entity_asset_id`, "face groups do not partition triangle GLB indices"));
    if (edgeInfo !== undefined && edgeTotal !== edgeInfo.indexCount) issues.push(issue("entity_range_invalid", `/definitions/${definitionIndex}/entity_asset_id`, "edge groups do not partition line GLB indices"));
  });
  return report(issues, "package");
}
