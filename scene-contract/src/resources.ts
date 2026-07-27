export const BASE_LIMITS = {
  zip_members: 50_000,
  input_archive_bytes: 256 * 1024 * 1024,
  canonical_archive_bytes: 256 * 1024 * 1024,
  total_uncompressed_bytes: 1024 * 1024 * 1024,
  one_member_bytes: 256 * 1024 * 1024,
  scene_json_bytes: 32 * 1024 * 1024,
  entity_json_bytes: 64 * 1024 * 1024,
  model_json_bytes: 64 * 1024 * 1024,
  presentation_json_bytes: 8 * 1024 * 1024,
  compression_ratio: 100,
  json_depth: 64,
  json_string_bytes: 1024 * 1024,
  uri_bytes: 1024,
  structural_id_bytes: 4096,
  definitions: 25_000,
  nodes: 100_000,
  assets_per_kind: 25_000,
  appearances: 25_000,
  connectors: 100_000,
  cameras: 1000,
  hierarchy_depth: 256,
  forwarded_connector_depth: 64,
  entities_per_sidecar: 500_000,
  entities_total: 2_000_000,
  triangle_vertices_per_asset: 2_000_000,
  triangle_vertices_total: 10_000_000,
  triangles_per_asset: 2_000_000,
  triangles_total: 10_000_000,
  line_vertices_per_asset: 2_000_000,
  line_vertices_total: 10_000_000,
  line_segments_per_asset: 2_000_000,
  line_segments_total: 10_000_000,
  static_decoded_buffer_bytes: 512 * 1024 * 1024,
} as const;

export type SceneResourceLimits = { readonly [Name in keyof typeof BASE_LIMITS]: number };
export type SceneResourceLimitName = keyof typeof BASE_LIMITS;

export function preflightInputArchiveSize(size: number, limits: SceneResourceLimits = BASE_LIMITS): number {
  if (!Number.isSafeInteger(size) || size < 0) throw new Error("invalid input archive size");
  if (size > limits.input_archive_bytes) throw new Error("input archive exceeds resource limit");
  return size;
}

export function preflightResourceCount(
  count: number,
  limitName: SceneResourceLimitName,
  limits: SceneResourceLimits = BASE_LIMITS,
): number {
  if (!Number.isSafeInteger(count) || count < 0) throw new Error("invalid resource count");
  if (count > limits[limitName]) throw new Error(`${limitName} exceeds resource limit`);
  return count;
}

export function preflightAggregateCompressionRatio(
  uncompressedSize: number,
  archiveSize: number,
  limits: SceneResourceLimits = BASE_LIMITS,
): void {
  if (!Number.isSafeInteger(uncompressedSize) || uncompressedSize < 0 || !Number.isSafeInteger(archiveSize) || archiveSize <= 0) {
    throw new Error("invalid compression ratio sizes");
  }
  if (uncompressedSize > limits.compression_ratio * archiveSize) throw new Error("aggregate compression ratio exceeds limit");
}

export function preflightMemberCompressionRatio(
  uncompressedSize: number,
  compressedSize: number,
  limits: SceneResourceLimits = BASE_LIMITS,
): void {
  if (!Number.isSafeInteger(uncompressedSize) || uncompressedSize < 0 || !Number.isSafeInteger(compressedSize) || compressedSize < 0) {
    throw new Error("invalid compression ratio sizes");
  }
  if (uncompressedSize > limits.compression_ratio * Math.max(1, compressedSize)) throw new Error("member compression ratio exceeds limit");
}
