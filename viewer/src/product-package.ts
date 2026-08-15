import { strFromU8, unzipSync } from 'fflate';

export type PackageFiles = Record<string, Uint8Array>;

export type OpenedCadPackage = {
  files: PackageFiles;
  packageContentHash: string;
};

type HashRecord = {
  uri?: string;
  path?: string;
  sha256: string;
  byte_length: number;
};

type ProductManifest = {
  schema_version: string;
  artifact_kind: string;
  content_hash: string;
  root: string;
  objects: ProductObject[];
  scene: HashRecord & { scene_id: string; revision: string };
};

type SceneProductAsset = HashRecord & {
  definition_id: string;
  definition_kind: 'single_solid' | 'assembly';
  revision: string;
  content_hash: string;
};

type SceneManifest = {
  schema_version: string;
  scene_id: string;
  revision: string;
  geometry_assets: HashRecord[];
  entity_assets: HashRecord[];
  product_assets: SceneProductAsset[];
  feature_graph_assets: HashRecord[];
  source_assets: HashRecord[];
};

type ProductObject = HashRecord & {
  definition_id: string;
  definition_kind: 'single_solid' | 'assembly';
  revision: string;
  content_hash: string;
};

const MAX_PACKAGE_BYTES = 256 * 1024 * 1024;
const MAX_PACKAGE_MEMBERS = 10_000;
const MAX_UNPACKED_BYTES = 512 * 1024 * 1024;
const MAX_MEMBER_BYTES = 256 * 1024 * 1024;
const MAX_MANIFEST_BYTES = 32 * 1024 * 1024;
const MAX_COMPRESSION_RATIO = 100;

function validateMemberName(name: string): void {
  if (!/^[A-Za-z0-9][A-Za-z0-9._/-]{0,4095}$/.test(name)
    || name.split('/').some((segment) => !segment || segment === '.' || segment === '..')) {
    throw new Error(`invalid package member: ${name}`);
  }
}

function extractArchive(raw: Uint8Array, manifestNames: readonly string[]): PackageFiles {
  if (raw.byteLength > MAX_PACKAGE_BYTES) throw new Error('package exceeds browser size limit');
  let memberCount = 0;
  let unpackedBytes = 0;
  const seenNames = new Set<string>();
  unzipSync(raw, { filter: (entry) => {
    validateMemberName(entry.name);
    const foldedName = entry.name.toLowerCase();
    if (seenNames.has(foldedName)) throw new Error(`duplicate or case-colliding package member: ${entry.name}`);
    seenNames.add(foldedName);
    memberCount += 1;
    unpackedBytes += entry.originalSize;
    if (entry.compression !== 0 && entry.compression !== 8) throw new Error(`unsupported ZIP compression method: ${entry.name}`);
    if (memberCount > MAX_PACKAGE_MEMBERS) throw new Error('package member count exceeds browser limit');
    if (entry.originalSize > MAX_MEMBER_BYTES) throw new Error(`package member exceeds browser size limit: ${entry.name}`);
    if (manifestNames.includes(entry.name) && entry.originalSize > MAX_MANIFEST_BYTES) throw new Error(`${entry.name} is too large`);
    if (unpackedBytes > MAX_UNPACKED_BYTES) throw new Error('package expands beyond browser size limit');
    if (entry.originalSize > MAX_COMPRESSION_RATIO * Math.max(1, entry.size)) throw new Error(`package member compression ratio is too high: ${entry.name}`);
    return false;
  }});
  const presentManifests = manifestNames.filter((name) => seenNames.has(name.toLowerCase()));
  if (presentManifests.length !== 1) throw new Error('package must contain exactly one supported manifest');
  if (unpackedBytes > MAX_COMPRESSION_RATIO * raw.byteLength) throw new Error('package compression ratio is too high');
  const files = unzipSync(raw) as PackageFiles;
  const entries = Object.entries(files);
  if (entries.length !== memberCount) throw new Error('package member count changed during extraction');
  if (entries.reduce((sum, [, value]) => sum + value.byteLength, 0) !== unpackedBytes) {
    throw new Error('package decoded size differs from ZIP metadata');
  }
  return files;
}

function parseManifest<T>(files: PackageFiles, name: string): T {
  const payload = files[name];
  if (!payload || payload.byteLength > MAX_MANIFEST_BYTES) throw new Error(`${name} is missing or too large`);
  let value: unknown;
  try {
    value = JSON.parse(strFromU8(payload));
  } catch {
    throw new Error(`${name} is not valid JSON`);
  }
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${name} must contain an object`);
  return value as T;
}

function recordPath(record: HashRecord): string {
  const path = record.uri ?? record.path;
  if (typeof path !== 'string') throw new Error('package record path is missing');
  validateMemberName(path);
  return path;
}

function canonicalJson(value: unknown): string {
  if (value === null || typeof value === 'boolean' || typeof value === 'string') return JSON.stringify(value);
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new Error('manifest contains a non-finite number');
    return JSON.stringify(value);
  }
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`;
  if (typeof value !== 'object') throw new Error('manifest contains a non-JSON value');
  const object = value as Record<string, unknown>;
  return `{${Object.keys(object).sort().map((key) => `${JSON.stringify(key)}:${canonicalJson(object[key])}`).join(',')}}`;
}

async function sha256(payload: Uint8Array): Promise<string> {
  const view = payload.buffer.slice(payload.byteOffset, payload.byteOffset + payload.byteLength) as ArrayBuffer;
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', view));
  return `sha256:${Array.from(bytes, (byte) => byte.toString(16).padStart(2, '0')).join('')}`;
}

async function canonicalHash(value: unknown): Promise<string> {
  return sha256(new TextEncoder().encode(canonicalJson(value)));
}

async function validateRecords(files: PackageFiles, records: HashRecord[], manifestName: string): Promise<void> {
  const referenced = new Set<string>([manifestName]);
  for (const record of records) {
    const path = recordPath(record);
    if (referenced.has(path)) throw new Error(`duplicate package reference: ${path}`);
    referenced.add(path);
    const payload = files[path];
    if (!payload) throw new Error(`package member is missing: ${path}`);
    if (!Number.isSafeInteger(record.byte_length) || record.byte_length < 0 || payload.byteLength !== record.byte_length) {
      throw new Error(`package member length differs: ${path}`);
    }
    if (!/^sha256:[0-9a-f]{64}$/.test(record.sha256) || await sha256(payload) !== record.sha256) {
      throw new Error(`package member hash differs: ${path}`);
    }
  }
  const names = Object.keys(files);
  if (names.length !== referenced.size || names.some((name) => !referenced.has(name))) {
    throw new Error(`${manifestName} references do not match package members`);
  }
}

async function validateScene(files: PackageFiles): Promise<SceneManifest> {
  const manifest = parseManifest<SceneManifest>(files, 'scene.json');
  if (manifest.schema_version !== '2.0') throw new Error(`unsupported scene schema: ${manifest.schema_version}`);
  if (typeof manifest.scene_id !== 'string' || typeof manifest.revision !== 'string') throw new Error('scene identity is incomplete');
  const collections = [manifest.geometry_assets, manifest.entity_assets, manifest.product_assets, manifest.feature_graph_assets, manifest.source_assets];
  if (collections.some((items) => !Array.isArray(items))) throw new Error('scene asset collections are incomplete');
  await validateRecords(files, collections.flat(), 'scene.json');
  const draft = { ...manifest } as Record<string, unknown>;
  delete draft.revision;
  if (manifest.revision !== await canonicalHash(draft)) throw new Error('scene revision is invalid');
  return manifest;
}
async function validateProductSceneClosure(product: ProductManifest, scene: SceneManifest): Promise<void> {
  const identity = (record: {
    definition_kind: string;
    definition_id: string;
    revision: string;
    content_hash: string;
  }): string => [record.definition_kind, record.definition_id, record.revision, record.content_hash].join('\u0000');
  const objectIdentities = product.objects.map(identity).sort();
  const sceneIdentities = scene.product_assets.map(identity).sort();
  if (objectIdentities.length !== sceneIdentities.length
    || objectIdentities.some((item, index) => item !== sceneIdentities[index])) {
    throw new Error('product package definitions differ from embedded scene product assets');
  }
}

async function openScene(raw: Uint8Array): Promise<{ files: PackageFiles; manifest: SceneManifest }> {
  const files = extractArchive(raw, ['scene.json']);
  return { files, manifest: await validateScene(files) };
}

export async function openCadPackage(raw: Uint8Array): Promise<OpenedCadPackage> {
  const outer = extractArchive(raw, ['package.json']);
  const manifest = parseManifest<ProductManifest>(outer, 'package.json');
  if (manifest.schema_version !== '2.0' || manifest.artifact_kind !== 'product_package') throw new Error('unsupported product package schema');
  if (!Array.isArray(manifest.objects) || !manifest.scene || typeof manifest.scene !== 'object') throw new Error('product package records are incomplete');
  await validateRecords(outer, [...manifest.objects, manifest.scene], 'package.json');
  const draft = { ...manifest } as Record<string, unknown>;
  delete draft.content_hash;
  if (manifest.content_hash !== await canonicalHash(draft)) throw new Error('product package content hash is invalid');
  const scenePath = recordPath(manifest.scene);
  if (scenePath !== 'scene/scene.zip') throw new Error('product package scene path is not canonical');
  const scene = await openScene(outer[scenePath]);
  if (scene.manifest.scene_id !== manifest.scene.scene_id || scene.manifest.revision !== manifest.scene.revision) {
    throw new Error('embedded scene identity differs from package record');
  }
  await validateProductSceneClosure(manifest, scene.manifest);
  return { files: scene.files, packageContentHash: manifest.content_hash };
}
