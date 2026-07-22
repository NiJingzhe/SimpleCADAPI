import { canonicalJsonBytes, parseStrictJson } from "./canonical.js";
import { BASE_LIMITS, type SceneResourceLimits } from "./resources.js";

export type GlbKind = "triangle" | "line";

export interface GlbInfo {
  kind: GlbKind;
  vertexCount: number;
  indexCount: number;
  primitiveCount: number;
  decodedBufferBytes: number;
  positionBounds: readonly [readonly [number, number, number], readonly [number, number, number]];
}

const maxSafeInteger = 9_007_199_254_740_991;

function record(value: unknown, context: string): Record<string, unknown> {
  if (value === null || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${context} must be an object`);
  }
  return value as Record<string, unknown>;
}

function requireKeys(value: unknown, expected: readonly string[], context: string): Record<string, unknown> {
  const result = record(value, context);
  const keys = Object.keys(result).sort();
  if (keys.length !== expected.length || keys.some((key, index) => key !== [...expected].sort()[index])) {
    throw new Error(`${context} fields do not match closed GLB profile`);
  }
  return result;
}

function integer(value: unknown, context: string): number {
  if (!Number.isSafeInteger(value) || typeof value !== "number" || value < 0 || value > maxSafeInteger) {
    throw new Error(`${context} must be a non-negative safe integer`);
  }
  return value;
}

function vec3(value: unknown, context: string): [number, number, number] {
  if (
    !Array.isArray(value) ||
    value.length !== 3 ||
    value.some((component) => typeof component !== "number")
  ) {
    throw new Error(`${context} must be a three-number array`);
  }
  if (!value.every(Number.isFinite)) throw new Error(`${context} must contain finite values`);
  return value as [number, number, number];
}

export function profileF32Bits(value: number): number {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error("f32 input must be a finite number");
  const converted = Math.fround(value);
  if (!Number.isFinite(converted)) throw new Error("f32 conversion overflowed");
  const bytes = Buffer.allocUnsafe(4);
  bytes.writeFloatLE(converted, 0);
  const bits = bytes.readUInt32LE();
  return bits === 0x80000000 ? 0 : bits;
}

export function profileF32(value: number): number {
  const bytes = Buffer.allocUnsafe(4);
  bytes.writeUInt32LE(profileF32Bits(value));
  return bytes.readFloatLE();
}

export function profileCross(
  left: readonly [number, number, number],
  right: readonly [number, number, number],
): [number, number, number] {
  const a = vec3(left, "cross left");
  const b = vec3(right, "cross right");
  const p1x = a[1] * b[2];
  const p2x = a[2] * b[1];
  const p1y = a[2] * b[0];
  const p2y = a[0] * b[2];
  const p1z = a[0] * b[1];
  const p2z = a[1] * b[0];
  const result: [number, number, number] = [p1x - p2x, p1y - p2y, p1z - p2z];
  if (!result.every(Number.isFinite)) throw new Error("cross product produced a non-finite value");
  return result;
}

export function profileNormalize(value: readonly [number, number, number]): [number, number, number] {
  const vector = vec3(value, "normalize input");
  let squared = vector[0] * vector[0] + vector[1] * vector[1];
  squared += vector[2] * vector[2];
  if (!Number.isFinite(squared) || squared <= 0) throw new Error("normalize input has zero or non-finite length");
  const length = Math.sqrt(squared);
  const result: [number, number, number] = vector.map((component) => profileF32(component / length)) as [number, number, number];
  let normSquared = result[0] * result[0] + result[1] * result[1];
  normSquared += result[2] * result[2];
  const norm = Math.sqrt(normSquared);
  if (norm < 1 - 1e-6 || norm > 1 + 1e-6) throw new Error("normalized binary32 vector is outside the profile tolerance");
  return result;
}

function array(value: unknown, context: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${context} must be an array`);
  return value;
}

function equalArray(left: readonly unknown[], right: readonly unknown[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index]);
}

function tupleCompare(left: readonly number[], right: readonly number[]): number {
  for (let index = 0; index < left.length; index += 1) {
    if (left[index] !== right[index]) return left[index] - right[index];
  }
  return 0;
}

export function preflightGlbCounts(
  kind: GlbKind,
  vertexCountInput: number,
  indexCountInput: number,
  limits: SceneResourceLimits = BASE_LIMITS,
): number {
  const vertexCount = integer(vertexCountInput, "POSITION count");
  const vertexLimit = kind === "triangle"
    ? limits.triangle_vertices_per_asset
    : limits.line_vertices_per_asset;
  if (vertexCount === 0 || vertexCount > vertexLimit) {
    throw new Error("GLB vertex count is empty or exceeds resource limit");
  }
  const indexCount = integer(indexCountInput, "index count");
  const divisor = kind === "triangle" ? 3 : 2;
  const primitiveCount = indexCount / divisor;
  const primitiveLimit = kind === "triangle"
    ? limits.triangles_per_asset
    : limits.line_segments_per_asset;
  if (indexCount === 0 || indexCount % divisor !== 0 || primitiveCount > primitiveLimit) {
    throw new Error("GLB index count is invalid or exceeds resource limit");
  }
  return primitiveCount;
}

export function preflightGlb(
  data: Uint8Array,
  expectedKind?: GlbKind,
  limits: SceneResourceLimits = BASE_LIMITS,
): GlbInfo {
  if (data.byteLength > limits.one_member_bytes) throw new Error("GLB exceeds resource limit");
  const raw = Buffer.from(data);
  if (raw.length < 28) throw new Error("truncated GLB");
  if (raw.readUInt32LE(0) !== 0x46546c67 || raw.readUInt32LE(4) !== 2 || raw.readUInt32LE(8) !== raw.length) {
    throw new Error("invalid GLB header");
  }
  const jsonLength = raw.readUInt32LE(12);
  if (raw.readUInt32LE(16) !== 0x4e4f534a || jsonLength % 4 !== 0) {
    throw new Error("invalid GLB JSON chunk header");
  }
  const jsonEnd = 20 + jsonLength;
  if (jsonEnd + 8 > raw.length) throw new Error("truncated GLB JSON chunk");
  const paddedJson = raw.subarray(20, jsonEnd);
  let unpaddedLength = paddedJson.length;
  while (unpaddedLength > 0 && paddedJson[unpaddedLength - 1] === 0x20) unpaddedLength -= 1;
  const jsonBytes = paddedJson.subarray(0, unpaddedLength);
  const expectedPadding = (4 - (jsonBytes.length % 4)) % 4;
  if (
    paddedJson.length !== jsonBytes.length + expectedPadding ||
    paddedJson.subarray(jsonBytes.length).some((byte) => byte !== 0x20)
  ) {
    throw new Error("GLB JSON padding must use the minimal ASCII-space suffix");
  }
  const document = parseStrictJson(jsonBytes);
  if (document === null || typeof document !== "object" || Array.isArray(document) || !Buffer.from(jsonBytes).equals(canonicalJsonBytes(document))) {
    throw new Error("GLB JSON chunk must be RFC 8785 canonical");
  }
  const binLength = raw.readUInt32LE(jsonEnd);
  if (raw.readUInt32LE(jsonEnd + 4) !== 0x004e4942 || binLength % 4 !== 0 || jsonEnd + 8 + binLength !== raw.length) {
    throw new Error("invalid GLB BIN chunk header");
  }
  const binData = raw.subarray(jsonEnd + 8);
  const root = requireKeys(
    document,
    ["accessors", "asset", "bufferViews", "buffers", "meshes", "nodes", "scene", "scenes"],
    "GLB root",
  );
  const asset = root.asset;
  if (JSON.stringify(asset) !== JSON.stringify({ generator: "SimpleCAD Scene GLB Profile 1", version: "2.0" })) {
    throw new Error("GLB asset record does not match Scene profile");
  }
  const nodes = array(root.nodes, "GLB nodes");
  const scenes = array(root.scenes, "GLB scenes");
  let skeletonValid = integer(root.scene, "GLB default scene") === 0 && nodes.length === 1 && scenes.length === 1;
  if (skeletonValid) {
    const node = requireKeys(nodes[0], ["mesh"], "GLB node");
    const scene = requireKeys(scenes[0], ["nodes"], "GLB scene");
    skeletonValid = integer(node.mesh, "GLB node mesh") === 0 && Array.isArray(scene.nodes) && equalArray(scene.nodes, [0]);
    if (Array.isArray(scene.nodes) && scene.nodes.some((item) => !Number.isSafeInteger(item) || typeof item !== "number")) {
      skeletonValid = false;
    }
  }
  if (!skeletonValid) throw new Error("GLB scene/node skeleton does not match Scene profile");

  const meshes = array(root.meshes, "GLB meshes");
  if (meshes.length !== 1) throw new Error("GLB must contain exactly one mesh");
  const mesh = requireKeys(meshes[0], ["primitives"], "GLB mesh");
  const primitives = array(mesh.primitives, "GLB primitives");
  if (primitives.length !== 1) throw new Error("GLB must contain exactly one primitive");
  const primitive = requireKeys(primitives[0], ["attributes", "indices", "mode"], "GLB primitive");
  const accessors = array(root.accessors, "GLB accessors");
  const views = array(root.bufferViews, "GLB bufferViews");
  const buffers = array(root.buffers, "GLB buffers");
  if (buffers.length !== 1) throw new Error("GLB accessors/bufferViews/buffer skeleton is invalid");
  const buffer = requireKeys(buffers[0], ["byteLength"], "GLB buffer");
  const bufferByteLength = integer(buffer.byteLength, "GLB buffer byteLength");
  const attributesRecord = record(primitive.attributes, "GLB primitive attributes");
  const attributes = Object.fromEntries(
    Object.entries(attributesRecord).map(([name, value]) => [name, integer(value, `GLB ${name} attribute accessor`)]),
  );
  const primitiveIndices = integer(primitive.indices, "GLB primitive index accessor");
  const primitiveMode = integer(primitive.mode, "GLB primitive mode");
  let kind: GlbKind;
  let accessorCount: number;
  let indexView: number;
  if (JSON.stringify(attributes) === JSON.stringify({ NORMAL: 1, POSITION: 0 }) && primitiveIndices === 2 && primitiveMode === 4) {
    kind = "triangle";
    accessorCount = 3;
    indexView = 2;
  } else if (JSON.stringify(attributes) === JSON.stringify({ POSITION: 0 }) && primitiveIndices === 1 && primitiveMode === 1) {
    kind = "line";
    accessorCount = 2;
    indexView = 1;
  } else {
    throw new Error("GLB primitive does not match triangle or line profile");
  }
  if (expectedKind !== undefined && kind !== expectedKind) throw new Error(`expected ${expectedKind} GLB, got ${kind}`);
  if (accessors.length !== accessorCount || views.length !== accessorCount) {
    throw new Error("GLB accessor/bufferView count mismatch");
  }

  const position = requireKeys(accessors[0], ["bufferView", "componentType", "count", "max", "min", "type"], "POSITION accessor");
  const vertexCount = integer(position.count, "POSITION count");
  if (integer(position.bufferView, "POSITION bufferView") !== 0 || integer(position.componentType, "POSITION componentType") !== 5126 || position.type !== "VEC3") {
    throw new Error("invalid POSITION accessor");
  }
  const minimum = vec3(position.min, "POSITION min");
  const maximum = vec3(position.max, "POSITION max");
  if (minimum.some((value, index) => value > maximum[index])) throw new Error("POSITION min exceeds max");

  if (kind === "triangle") {
    const normal = requireKeys(accessors[1], ["bufferView", "componentType", "count", "type"], "NORMAL accessor");
    if (integer(normal.bufferView, "NORMAL bufferView") !== 1 || integer(normal.componentType, "NORMAL componentType") !== 5126 || integer(normal.count, "NORMAL count") !== vertexCount || normal.type !== "VEC3") {
      throw new Error("invalid NORMAL accessor");
    }
  }
  const indexAccessor = requireKeys(accessors[indexView], ["bufferView", "componentType", "count", "type"], "index accessor");
  const indexCount = integer(indexAccessor.count, "index count");
  const primitiveCount = preflightGlbCounts(kind, vertexCount, indexCount, limits);
  const componentType = vertexCount <= 65536 ? 5123 : 5125;
  if (integer(indexAccessor.bufferView, "index bufferView") !== indexView || integer(indexAccessor.componentType, "index componentType") !== componentType || indexAccessor.type !== "SCALAR") {
    throw new Error("invalid GLB index accessor");
  }

  let expectedOffset = 0;
  const parsedViews: Record<string, unknown>[] = [];
  for (let viewIndex = 0; viewIndex < views.length; viewIndex += 1) {
    const view = requireKeys(views[viewIndex], ["buffer", "byteLength", "byteOffset", "target"], `bufferView[${viewIndex}]`);
    parsedViews.push(view);
    const offset = integer(view.byteOffset, `bufferView[${viewIndex}].byteOffset`);
    const length = integer(view.byteLength, `bufferView[${viewIndex}].byteLength`);
    if (integer(view.buffer, `bufferView[${viewIndex}].buffer`) !== 0 || offset !== expectedOffset) throw new Error("GLB bufferView offset mismatch");
    if (integer(view.target, `bufferView[${viewIndex}].target`) !== (viewIndex < indexView ? 34962 : 34963)) throw new Error("GLB bufferView target mismatch");
    const expectedLength = viewIndex < indexView ? 12 * vertexCount : indexCount * (componentType === 5123 ? 2 : 4);
    if (length !== expectedLength) throw new Error("GLB bufferView byteLength mismatch");
    expectedOffset = (expectedOffset + expectedLength + 3) & ~3;
  }
  const lastView = parsedViews.at(-1)!;
  const unpaddedBinLength = integer(lastView.byteOffset, "last bufferView byteOffset") + integer(lastView.byteLength, "last bufferView byteLength");
  if (bufferByteLength !== unpaddedBinLength) throw new Error("GLB buffer byteLength mismatch");
  if (binLength !== ((unpaddedBinLength + 3) & ~3)) throw new Error("GLB BIN chunk length mismatch");
  if (binData.subarray(unpaddedBinLength).some((byte) => byte !== 0)) throw new Error("GLB BIN padding must be zero");

  const positions: [number, number, number][] = [];
  for (let index = 0; index < vertexCount; index += 1) {
    const offset = index * 12;
    const point: [number, number, number] = [binData.readFloatLE(offset), binData.readFloatLE(offset + 4), binData.readFloatLE(offset + 8)];
    if (!point.every(Number.isFinite)) throw new Error("GLB POSITION contains non-finite values");
    if ([0, 4, 8].some((delta) => binData.readUInt32LE(offset + delta) === 0x80000000)) throw new Error("GLB float buffers must encode zero with positive sign");
    positions.push(point);
  }
  const actualMin: [number, number, number] = [...positions[0]];
  const actualMax: [number, number, number] = [...positions[0]];
  for (const point of positions) {
    for (let axis = 0; axis < 3; axis += 1) {
      actualMin[axis] = Math.min(actualMin[axis], point[axis]);
      actualMax[axis] = Math.max(actualMax[axis], point[axis]);
    }
  }
  if (!equalArray(minimum, actualMin) || !equalArray(maximum, actualMax)) throw new Error("POSITION accessor bounds do not match buffer");

  if (kind === "triangle") {
    const normalOffset = integer(parsedViews[1].byteOffset, "NORMAL byteOffset");
    for (let index = 0; index < vertexCount; index += 1) {
      const offset = normalOffset + index * 12;
      const normal = [binData.readFloatLE(offset), binData.readFloatLE(offset + 4), binData.readFloatLE(offset + 8)];
      if ([0, 4, 8].some((delta) => binData.readUInt32LE(offset + delta) === 0x80000000)) throw new Error("GLB float buffers must encode zero with positive sign");
      const norm = Math.sqrt(normal.reduce((sum, component) => sum + component * component, 0));
      if (!normal.every(Number.isFinite) || norm < 1 - 1e-6 || norm > 1 + 1e-6) throw new Error("GLB NORMAL must be finite and normalized");
    }
  }
  const indices: number[] = [];
  const indexOffset = integer(parsedViews[indexView].byteOffset, "index byteOffset");
  for (let index = 0; index < indexCount; index += 1) {
    indices.push(componentType === 5123 ? binData.readUInt16LE(indexOffset + index * 2) : binData.readUInt32LE(indexOffset + index * 4));
  }
  let maximumIndex = -1;
  for (const index of indices) maximumIndex = Math.max(maximumIndex, index);
  if (maximumIndex >= vertexCount || new Set(indices).size !== vertexCount) throw new Error("GLB indices must be in range and reference every vertex");
  if (kind === "triangle") {
    const triangles: number[][] = [];
    for (let index = 0; index < indexCount; index += 3) {
      const triple = indices.slice(index, index + 3);
      const rotations = [triple, [triple[1], triple[2], triple[0]], [triple[2], triple[0], triple[1]]].sort(tupleCompare);
      if (!equalArray(triple, rotations[0])) throw new Error("GLB triangle indices are not in canonical cyclic rotation");
      const [a, b, c] = triple.map((item) => positions[item]);
      const ab = b.map((value, axis) => value - a[axis]);
      const ac = c.map((value, axis) => value - a[axis]);
      const cross = [ab[1] * ac[2] - ab[2] * ac[1], ab[2] * ac[0] - ab[0] * ac[2], ab[0] * ac[1] - ab[1] * ac[0]];
      if (equalArray(a, b) || equalArray(b, c) || equalArray(a, c) || cross.every((value) => value === 0)) throw new Error("GLB contains a collapsed triangle");
      triangles.push(triple);
    }
    const sorted = [...triangles].sort(tupleCompare);
    if (triangles.some((triple, index) => !equalArray(triple, sorted[index]))) throw new Error("GLB triangle records are not canonically sorted");
  } else {
    const segments: number[][] = [];
    for (let index = 0; index < indexCount; index += 2) {
      const pair = indices.slice(index, index + 2);
      if (pair[0] >= pair[1]) throw new Error("GLB line indices are not in canonical endpoint order");
      if (equalArray(positions[pair[0]], positions[pair[1]])) throw new Error("GLB contains a collapsed line segment");
      segments.push(pair);
    }
    const sortedUnique = [...new Map(segments.map((pair) => [pair.join(","), pair])).values()].sort(tupleCompare);
    if (segments.length !== sortedUnique.length || segments.some((pair, index) => !equalArray(pair, sortedUnique[index]))) throw new Error("GLB line records are not sorted and unique");
  }
  return {
    kind,
    vertexCount,
    indexCount,
    primitiveCount,
    decodedBufferBytes: 2 * parsedViews.reduce((sum, view) => sum + integer(view.byteLength, "bufferView byteLength"), 0),
    positionBounds: [minimum, maximum],
  };
}
