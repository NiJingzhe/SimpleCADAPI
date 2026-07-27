import assert from "node:assert/strict";
import test from "node:test";
import { BASE_LIMITS, preflightZipBytes } from "../src/index.js";

function declaredDeflateZip(
  compressed: Uint8Array,
  uncompressedSize: number,
  localUncompressedSize = uncompressedSize,
): Buffer {
  const name = Buffer.from("scene.json", "ascii");
  const local = Buffer.alloc(30);
  local.writeUInt32LE(0x04034b50, 0);
  local.writeUInt16LE(20, 4);
  local.writeUInt16LE(0x0800, 6);
  local.writeUInt16LE(8, 8);
  local.writeUInt16LE(0, 10);
  local.writeUInt16LE(0x0021, 12);
  local.writeUInt32LE(0, 14);
  local.writeUInt32LE(compressed.byteLength, 18);
  local.writeUInt32LE(localUncompressedSize, 22);
  local.writeUInt16LE(name.length, 26);
  local.writeUInt16LE(0, 28);

  const centralOffset = local.length + name.length + compressed.byteLength;
  const central = Buffer.alloc(46);
  central.writeUInt32LE(0x02014b50, 0);
  central.writeUInt16LE(0x0314, 4);
  central.writeUInt16LE(20, 6);
  central.writeUInt16LE(0x0800, 8);
  central.writeUInt16LE(8, 10);
  central.writeUInt16LE(0, 12);
  central.writeUInt16LE(0x0021, 14);
  central.writeUInt32LE(0, 16);
  central.writeUInt32LE(compressed.byteLength, 20);
  central.writeUInt32LE(uncompressedSize, 24);
  central.writeUInt16LE(name.length, 28);
  central.writeUInt16LE(0, 30);
  central.writeUInt16LE(0, 32);
  central.writeUInt16LE(0, 34);
  central.writeUInt16LE(0, 36);
  central.writeUInt32LE(0x81a40000, 38);
  central.writeUInt32LE(0, 42);

  const eocd = Buffer.alloc(22);
  eocd.writeUInt32LE(0x06054b50, 0);
  eocd.writeUInt16LE(0, 4);
  eocd.writeUInt16LE(0, 6);
  eocd.writeUInt16LE(1, 8);
  eocd.writeUInt16LE(1, 10);
  eocd.writeUInt32LE(central.length + name.length, 12);
  eocd.writeUInt32LE(centralOffset, 16);
  eocd.writeUInt16LE(0, 20);
  return Buffer.concat([local, name, compressed, central, name, eocd]);
}

function assertError(archive: Uint8Array, expected: string): void {
  assert.throws(() => preflightZipBytes(archive), (error) => {
    assert.equal((error as Error).message, expected);
    return true;
  });
}

test("aggregate ratio uses cross-checked declarations before inflate", () => {
  const compressed = Buffer.from([0]);
  const template = declaredDeflateZip(compressed, 0);
  const exactSize = template.length * BASE_LIMITS.compression_ratio;

  assertError(
    declaredDeflateZip(compressed, exactSize),
    'member compression ratio exceeds limit: "scene.json"',
  );
  assertError(
    declaredDeflateZip(compressed, exactSize + 1),
    "aggregate compression ratio exceeds limit",
  );
  assertError(
    declaredDeflateZip(compressed, exactSize + 1, exactSize),
    "ZIP central/local header mismatch",
  );
});

test("zero compressed size uses one as the member ratio denominator", () => {
  assertError(
    declaredDeflateZip(Buffer.alloc(0), BASE_LIMITS.compression_ratio),
    'invalid deflate stream: "scene.json"',
  );
  assertError(
    declaredDeflateZip(Buffer.alloc(0), BASE_LIMITS.compression_ratio + 1),
    'member compression ratio exceeds limit: "scene.json"',
  );
});
