import { inflateRawSync } from "node:zlib";
import {
  BASE_LIMITS,
  preflightAggregateCompressionRatio,
  preflightInputArchiveSize,
  preflightMemberCompressionRatio,
  type SceneResourceLimits,
} from "./resources.js";

export interface ArchiveInfo {
  members: ReadonlyMap<string, Buffer>;
  inputSize: number;
  canonicalSize: number;
  usedDeflate: boolean;
}

interface Entry {
  name: string;
  method: number;
  crc32: number;
  compressedSize: number;
  uncompressedSize: number;
  localOffset: number;
}

const memberPattern = /^[A-Za-z0-9][A-Za-z0-9._/-]{0,1023}$/;
function crc32Table(): Uint32Array {
  const table = new Uint32Array(256);
  for (let index = 0; index < 256; index += 1) {
    let value = index;
    for (let bit = 0; bit < 8; bit += 1) value = (value & 1) !== 0 ? 0xedb88320 ^ (value >>> 1) : value >>> 1;
    table[index] = value >>> 0;
  }
  return table;
}

const crcTable = crc32Table();

function crc32(data: Uint8Array): number {
  let crc = 0xffffffff;
  for (const byte of data) crc = crcTable[(crc ^ byte) & 0xff] ^ (crc >>> 8);
  return (crc ^ 0xffffffff) >>> 0;
}

function ascii(raw: Uint8Array, context: string): string {
  if (raw.some((byte) => byte > 0x7f)) throw new Error("archive member names must be ASCII");
  return Buffer.from(raw).toString("ascii");
}

function validateName(name: string, seen: Set<string>): Buffer {
  const encoded = Buffer.from(name, "ascii");
  if (encoded.toString("ascii") !== name) throw new Error("archive member names must be ASCII");
  if (!memberPattern.test(name)) throw new Error(`invalid archive member name: ${JSON.stringify(name)}`);
  if (name.split("/").some((segment) => segment === "" || segment === "." || segment === "..")) {
    throw new Error(`invalid archive member path segment: ${JSON.stringify(name)}`);
  }
  const folded = name.toLowerCase();
  if (seen.has(folded)) throw new Error(`duplicate or case-colliding archive member: ${JSON.stringify(name)}`);
  seen.add(folded);
  return encoded;
}

export function canonicalArchiveSize(sizes: ReadonlyMap<string, number>): number {
  let total = 22;
  for (const [name, size] of sizes) total += 76 + 2 * Buffer.byteLength(name, "ascii") + size;
  return total;
}

export function preflightArchiveMemberSizes(
  sizes: ReadonlyMap<string, number>,
  limits: SceneResourceLimits = BASE_LIMITS,
): number {
  if (sizes.size === 0 || !sizes.has("scene.json")) throw new Error("scene package must contain scene.json");
  if (sizes.size > limits.zip_members) throw new Error("archive member count exceeds resource limit");
  const seen = new Set<string>();
  let total = 0;
  for (const [name, size] of sizes) {
    validateName(name, seen);
    if (!Number.isSafeInteger(size) || size < 0) throw new Error(`invalid member size for ${JSON.stringify(name)}`);
    if (size > limits.one_member_bytes) throw new Error(`archive member exceeds resource limit: ${JSON.stringify(name)}`);
    if (name === "scene.json" && size > limits.scene_json_bytes) throw new Error("scene.json exceeds resource limit");
    if (name.startsWith("entities/") && size > limits.entity_json_bytes) throw new Error(`entity sidecar exceeds resource limit: ${JSON.stringify(name)}`);
    if (name === "model/model.json" && size > limits.model_json_bytes) throw new Error("embedded model.json exceeds resource limit");
    if (name === "presentation/presentation.json" && size > limits.presentation_json_bytes) throw new Error("presentation JSON exceeds resource limit");
    total += size;
    if (total > limits.total_uncompressed_bytes) throw new Error("total uncompressed bytes exceed resource limit");
  }
  const result = canonicalArchiveSize(sizes);
  if (result > limits.canonical_archive_bytes) throw new Error("canonical stored archive exceeds resource limit");
  if (sizes.size > 0xffff || result > 0xffffffff) throw new Error("archive would require ZIP64");
  return result;
}

export function canonicalZipBytes(
  input: ReadonlyMap<string, Uint8Array> | Record<string, Uint8Array>,
  limits: SceneResourceLimits = BASE_LIMITS,
): Buffer {
  const members = input instanceof Map ? new Map(input) : new Map(Object.entries(input));
  const payloads = new Map([...members].map(([name, value]) => [name, Buffer.from(value)]));
  const canonicalSize = preflightArchiveMemberSizes(new Map([...payloads].map(([name, value]) => [name, value.length])), limits);
  const localParts: Buffer[] = [];
  const centralParts: Buffer[] = [];
  let localOffset = 0;
  for (const name of [...payloads.keys()].sort((left, right) => Buffer.compare(Buffer.from(left, "ascii"), Buffer.from(right, "ascii")))) {
    const nameBytes = Buffer.from(name, "ascii");
    const payload = payloads.get(name)!;
    const crc = crc32(payload);
    const local = Buffer.alloc(30);
    local.writeUInt32LE(0x04034b50, 0);
    local.writeUInt16LE(20, 4);
    local.writeUInt16LE(0x0800, 6);
    local.writeUInt16LE(0, 8);
    local.writeUInt16LE(0, 10);
    local.writeUInt16LE(0x0021, 12);
    local.writeUInt32LE(crc, 14);
    local.writeUInt32LE(payload.length, 18);
    local.writeUInt32LE(payload.length, 22);
    local.writeUInt16LE(nameBytes.length, 26);
    local.writeUInt16LE(0, 28);
    localParts.push(local, nameBytes, payload);
    const central = Buffer.alloc(46);
    central.writeUInt32LE(0x02014b50, 0);
    central.writeUInt16LE(0x0314, 4);
    central.writeUInt16LE(20, 6);
    central.writeUInt16LE(0x0800, 8);
    central.writeUInt16LE(0, 10);
    central.writeUInt16LE(0, 12);
    central.writeUInt16LE(0x0021, 14);
    central.writeUInt32LE(crc, 16);
    central.writeUInt32LE(payload.length, 20);
    central.writeUInt32LE(payload.length, 24);
    central.writeUInt16LE(nameBytes.length, 28);
    central.writeUInt16LE(0, 30);
    central.writeUInt16LE(0, 32);
    central.writeUInt16LE(0, 34);
    central.writeUInt16LE(0, 36);
    central.writeUInt32LE(0x81a40000, 38);
    central.writeUInt32LE(localOffset, 42);
    centralParts.push(central, nameBytes);
    localOffset += local.length + nameBytes.length + payload.length;
  }
  const centralBytes = Buffer.concat(centralParts);
  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(payloads.size, 8);
  eocd.writeUInt16LE(payloads.size, 10);
  eocd.writeUInt32LE(centralBytes.length, 12);
  eocd.writeUInt32LE(localOffset, 16);
  eocd.writeUInt16LE(0, 20);
  const result = Buffer.concat([...localParts, centralBytes, eocd]);
  if (result.length !== canonicalSize) throw new Error("canonical ZIP size formula disagrees with encoder");
  return result;
}

export function preflightZipBytes(data: Uint8Array, limits: SceneResourceLimits = BASE_LIMITS): ArchiveInfo {
  preflightInputArchiveSize(data.byteLength, limits);
  const raw = Buffer.isBuffer(data) ? data : Buffer.from(data);
  if (raw.length < 22) throw new Error("truncated ZIP archive");
  const eocdOffset = raw.length - 22;
  if (raw.readUInt32LE(eocdOffset) !== 0x06054b50 || raw.readUInt16LE(eocdOffset + 20) !== 0) {
    throw new Error("ZIP EOCD must be final and have no comment");
  }
  const disk = raw.readUInt16LE(eocdOffset + 4);
  const centralDisk = raw.readUInt16LE(eocdOffset + 6);
  const diskCount = raw.readUInt16LE(eocdOffset + 8);
  const totalCount = raw.readUInt16LE(eocdOffset + 10);
  const centralSize = raw.readUInt32LE(eocdOffset + 12);
  const centralOffset = raw.readUInt32LE(eocdOffset + 16);
  if (disk !== 0 || centralDisk !== 0 || diskCount !== totalCount) throw new Error("multi-disk ZIP archives are forbidden");
  if (totalCount > limits.zip_members) throw new Error("archive member count exceeds resource limit");
  if (centralOffset + centralSize !== eocdOffset) throw new Error("ZIP central directory offset/size mismatch");
  const entries: Entry[] = [];
  const seen = new Set<string>();
  let cursor = centralOffset;
  for (let index = 0; index < totalCount; index += 1) {
    if (cursor + 46 > eocdOffset) throw new Error("truncated ZIP central directory");
    if (raw.readUInt32LE(cursor) !== 0x02014b50) throw new Error("invalid ZIP central header signature");
    const madeBy = raw.readUInt16LE(cursor + 4);
    const needed = raw.readUInt16LE(cursor + 6);
    const flags = raw.readUInt16LE(cursor + 8);
    const method = raw.readUInt16LE(cursor + 10);
    const dosTime = raw.readUInt16LE(cursor + 12);
    const dosDate = raw.readUInt16LE(cursor + 14);
    const crc = raw.readUInt32LE(cursor + 16);
    const compressedSize = raw.readUInt32LE(cursor + 20);
    const uncompressedSize = raw.readUInt32LE(cursor + 24);
    const nameLength = raw.readUInt16LE(cursor + 28);
    const extraLength = raw.readUInt16LE(cursor + 30);
    const commentLength = raw.readUInt16LE(cursor + 32);
    const diskStart = raw.readUInt16LE(cursor + 34);
    const internalAttributes = raw.readUInt16LE(cursor + 36);
    const externalAttributes = raw.readUInt32LE(cursor + 38);
    const localOffset = raw.readUInt32LE(cursor + 42);
    if (madeBy !== 0x0314 || needed !== 20) throw new Error("ZIP creator/version profile mismatch");
    if (flags !== 0x0800 || (method !== 0 && method !== 8)) throw new Error("unsupported ZIP flags or compression method");
    if (dosTime !== 0 || dosDate !== 0x0021) throw new Error("ZIP timestamp profile mismatch");
    if (extraLength !== 0 || commentLength !== 0 || diskStart !== 0 || internalAttributes !== 0) throw new Error("ZIP extra/comment/disk/attributes are forbidden");
    if (externalAttributes !== 0x81a40000) throw new Error("ZIP member must be Unix regular mode 0100644");
    const nameStart = cursor + 46;
    const recordEnd = nameStart + nameLength + extraLength + commentLength;
    if (recordEnd > eocdOffset) throw new Error("truncated ZIP central member record");
    const name = ascii(raw.subarray(nameStart, nameStart + nameLength), "central name");
    validateName(name, seen);
    entries.push({ name, method, crc32: crc, compressedSize, uncompressedSize, localOffset });
    cursor = recordEnd;
  }
  if (cursor !== eocdOffset) throw new Error("unexpected bytes in ZIP central directory");
  const canonicalSize = preflightArchiveMemberSizes(new Map(entries.map((entry) => [entry.name, entry.uncompressedSize])), limits);
  const occupied: [number, number][] = [];
  const payloadRanges: { entry: Entry; start: number; end: number }[] = [];
  let totalUncompressed = 0;
  for (const entry of entries) {
    const offset = entry.localOffset;
    if (offset + 30 > centralOffset) throw new Error("truncated ZIP local header");
    if (raw.readUInt32LE(offset) !== 0x04034b50) throw new Error("invalid ZIP local header signature");
    const needed = raw.readUInt16LE(offset + 4);
    const flags = raw.readUInt16LE(offset + 6);
    const method = raw.readUInt16LE(offset + 8);
    const dosTime = raw.readUInt16LE(offset + 10);
    const dosDate = raw.readUInt16LE(offset + 12);
    const crc = raw.readUInt32LE(offset + 14);
    const compressedSize = raw.readUInt32LE(offset + 18);
    const uncompressedSize = raw.readUInt32LE(offset + 22);
    const nameLength = raw.readUInt16LE(offset + 26);
    const extraLength = raw.readUInt16LE(offset + 28);
    if (needed !== 20 || flags !== 0x0800 || method !== entry.method || dosTime !== 0 || dosDate !== 0x0021 || crc !== entry.crc32 || compressedSize !== entry.compressedSize || uncompressedSize !== entry.uncompressedSize || extraLength !== 0) {
      throw new Error("ZIP central/local header mismatch");
    }
    const nameStart = offset + 30;
    const nameEnd = nameStart + nameLength;
    const payloadEnd = nameEnd + compressedSize;
    if (payloadEnd > centralOffset) throw new Error("ZIP member payload crosses central directory");
    if (ascii(raw.subarray(nameStart, nameEnd), "local name") !== entry.name) throw new Error("ZIP central/local member name mismatch");
    occupied.push([offset, payloadEnd]);
    payloadRanges.push({ entry, start: nameEnd, end: payloadEnd });
    totalUncompressed += uncompressedSize;
  }
  occupied.sort((left, right) => left[0] - right[0]);
  if (occupied.length > 0) {
    if (occupied[0][0] !== 0) throw new Error("ZIP archive has a leading prefix");
    for (let index = 1; index < occupied.length; index += 1) {
      if (occupied[index - 1][1] !== occupied[index][0]) throw new Error("ZIP local records overlap or contain gaps");
    }
    if (occupied.at(-1)![1] !== centralOffset) throw new Error("ZIP bytes exist between local records and central directory");
  }
  preflightAggregateCompressionRatio(totalUncompressed, raw.length, limits);

  const members = new Map<string, Buffer>();
  for (const { entry, start, end } of payloadRanges) {
    const compressed = raw.subarray(start, end);
    try {
      preflightMemberCompressionRatio(entry.uncompressedSize, entry.compressedSize, limits);
    } catch {
      throw new Error(`member compression ratio exceeds limit: ${JSON.stringify(entry.name)}`);
    }
    let payload: Buffer;
    if (entry.method === 0) {
      payload = Buffer.from(compressed);
    } else {
      try {
        const inflated = inflateRawSync(compressed, { maxOutputLength: entry.uncompressedSize + 1, info: true }) as unknown as {
          buffer: Buffer;
          engine: { bytesWritten: number };
        };
        if (inflated.engine.bytesWritten !== compressed.length) throw new Error("trailing deflate data");
        payload = Buffer.from(inflated.buffer);
      } catch {
        throw new Error(`invalid deflate stream: ${JSON.stringify(entry.name)}`);
      }
    }
    if (payload.length !== entry.uncompressedSize) throw new Error(`ZIP member decoded size mismatch: ${JSON.stringify(entry.name)}`);
    if (crc32(payload) !== entry.crc32) throw new Error(`ZIP member CRC mismatch: ${JSON.stringify(entry.name)}`);
    members.set(entry.name, payload);
  }
  return { members, inputSize: raw.length, canonicalSize, usedDeflate: entries.some((entry) => entry.method === 8) };
}
