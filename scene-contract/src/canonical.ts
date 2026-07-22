import { createHash } from "node:crypto";

export class DuplicateKeyError extends SyntaxError {}

const decoder = new TextDecoder("utf-8", { fatal: true });
const maxSafeInteger = 9_007_199_254_740_991;
const parserDepthCapacity = 256;

function assertUnicodeScalarString(value: string): void {
  for (let index = 0; index < value.length; index += 1) {
    const unit = value.charCodeAt(index);
    if (unit >= 0xd800 && unit <= 0xdbff) {
      const next = value.charCodeAt(index + 1);
      if (!Number.isInteger(next) || next < 0xdc00 || next > 0xdfff) {
        throw new TypeError("string contains an unpaired surrogate");
      }
      index += 1;
    } else if (unit >= 0xdc00 && unit <= 0xdfff) {
      throw new TypeError("string contains an unpaired surrogate");
    }
  }
}

class StrictJsonParser {
  private offset = 0;

  public constructor(private readonly text: string) {}

  public parse(): unknown {
    this.space();
    const parsed = this.value(0);
    this.space();
    if (this.offset !== this.text.length) {
      throw new SyntaxError("trailing data after JSON value");
    }
    return parsed;
  }

  private value(depth: number): unknown {
    if (depth > parserDepthCapacity) {
      throw new SyntaxError("JSON nesting exceeds parser capacity");
    }
    this.space();
    const token = this.text[this.offset];
    if (
      this.text.startsWith("NaN", this.offset) ||
      this.text.startsWith("Infinity", this.offset) ||
      this.text.startsWith("-Infinity", this.offset)
    ) {
      throw new SyntaxError("non-finite JSON number is forbidden");
    }
    if (token === "{") return this.object(depth + 1);
    if (token === "[") return this.array(depth + 1);
    if (token === '"') return this.string();
    if (token === "t" && this.consume("true")) return true;
    if (token === "f" && this.consume("false")) return false;
    if (token === "n" && this.consume("null")) return null;
    if (token === "-" || (token !== undefined && token >= "0" && token <= "9")) {
      return this.number();
    }
    throw new SyntaxError(`invalid JSON token at offset ${this.offset}`);
  }

  private object(depth: number): Record<string, unknown> {
    this.offset += 1;
    this.space();
    const result: Record<string, unknown> = Object.create(null) as Record<string, unknown>;
    const keys = new Set<string>();
    if (this.text[this.offset] === "}") {
      this.offset += 1;
      return result;
    }
    while (true) {
      if (this.text[this.offset] !== '"') {
        throw new SyntaxError(`JSON object key expected at offset ${this.offset}`);
      }
      const key = this.string();
      if (keys.has(key)) {
        throw new DuplicateKeyError(`duplicate JSON object member: ${JSON.stringify(key)}`);
      }
      keys.add(key);
      this.space();
      if (this.text[this.offset] !== ":") {
        throw new SyntaxError(`JSON object colon expected at offset ${this.offset}`);
      }
      this.offset += 1;
      const child = this.value(depth);
      result[key] = child;
      this.space();
      const separator = this.text[this.offset];
      this.offset += 1;
      if (separator === "}") return result;
      if (separator !== ",") {
        throw new SyntaxError(`JSON object separator expected at offset ${this.offset - 1}`);
      }
      this.space();
    }
  }

  private array(depth: number): unknown[] {
    this.offset += 1;
    this.space();
    const result: unknown[] = [];
    if (this.text[this.offset] === "]") {
      this.offset += 1;
      return result;
    }
    while (true) {
      const child = this.value(depth);
      result.push(child);
      this.space();
      const separator = this.text[this.offset];
      this.offset += 1;
      if (separator === "]") return result;
      if (separator !== ",") {
        throw new SyntaxError(`JSON array separator expected at offset ${this.offset - 1}`);
      }
      this.space();
    }
  }

  private string(): string {
    const start = this.offset;
    this.offset += 1;
    while (this.offset < this.text.length) {
      const unit = this.text.charCodeAt(this.offset);
      if (unit < 0x20) {
        throw new SyntaxError(`unescaped control character at offset ${this.offset}`);
      }
      if (unit === 0x22) {
        this.offset += 1;
        const result = JSON.parse(this.text.slice(start, this.offset)) as string;
        assertUnicodeScalarString(result);
        return result;
      }
      if (unit === 0x5c) {
        this.offset += 1;
        const escape = this.text[this.offset];
        if (escape === "u") {
          if (!/^[0-9a-fA-F]{4}$/.test(this.text.slice(this.offset + 1, this.offset + 5))) {
            throw new SyntaxError(`invalid JSON Unicode escape at offset ${this.offset}`);
          }
          this.offset += 5;
          continue;
        }
        if (escape === undefined || !'"\\/bfnrt'.includes(escape)) {
          throw new SyntaxError(`invalid JSON escape at offset ${this.offset}`);
        }
      }
      this.offset += 1;
    }
    throw new SyntaxError("unterminated JSON string");
  }

  private number(): number {
    const match = /^-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?/.exec(
      this.text.slice(this.offset),
    );
    if (match === null) throw new SyntaxError(`invalid JSON number at offset ${this.offset}`);
    const token = match[0];
    this.offset += token.length;
    const result = Number(token);
    if (!/[.eE]/.test(token) && Math.abs(result) > maxSafeInteger) {
      throw new SyntaxError("JSON integer exceeds the JCS safe domain");
    }
    if (!Number.isFinite(result)) throw new SyntaxError("non-finite JSON number is forbidden");
    return result;
  }

  private consume(token: string): boolean {
    if (!this.text.startsWith(token, this.offset)) return false;
    this.offset += token.length;
    return true;
  }

  private space(): void {
    while (
      this.text[this.offset] === " " ||
      this.text[this.offset] === "\n" ||
      this.text[this.offset] === "\r" ||
      this.text[this.offset] === "\t"
    ) {
      this.offset += 1;
    }
  }
}

export function parseStrictJson(data: Uint8Array | string): unknown {
  let text: string;
  if (typeof data === "string") {
    text = data;
  } else {
    if (data.length >= 3 && data[0] === 0xef && data[1] === 0xbb && data[2] === 0xbf) {
      throw new SyntaxError("UTF-8 BOM is forbidden");
    }
    text = decoder.decode(data);
  }
  if (text.startsWith("\ufeff")) throw new SyntaxError("UTF-8 BOM is forbidden");
  return new StrictJsonParser(text).parse();
}

function serialize(value: unknown, stack: Set<object>): string {
  if (value === null) return "null";
  if (typeof value === "boolean") return value ? "true" : "false";
  if (typeof value === "number") {
    if (!Number.isFinite(value)) throw new TypeError("JSON number must be finite");
    return JSON.stringify(value);
  }
  if (typeof value === "string") {
    assertUnicodeScalarString(value);
    return JSON.stringify(value);
  }
  if (typeof value !== "object") throw new TypeError(`unsupported JSON value: ${typeof value}`);
  if (stack.has(value)) throw new TypeError("cyclic value is not JSON");
  stack.add(value);
  let result: string;
  if (Array.isArray(value)) {
    const items: string[] = [];
    for (let index = 0; index < value.length; index += 1) {
      if (!Object.hasOwn(value, index)) throw new TypeError("sparse arrays are outside the JSON domain");
      items.push(serialize(value[index], stack));
    }
    result = `[${items.join(",")}]`;
  } else {
    const record = value as Record<string, unknown>;
    const keys = Object.keys(record).sort();
    for (const key of keys) assertUnicodeScalarString(key);
    result = `{${keys
      .map((key) => `${JSON.stringify(key)}:${serialize(record[key], stack)}`)
      .join(",")}}`;
  }
  stack.delete(value);
  return result;
}

export function canonicalJsonBytes(value: unknown): Buffer {
  return Buffer.from(serialize(value, new Set()), "utf8");
}

export function parseCanonicalJson(data: Uint8Array | string): unknown {
  const raw = typeof data === "string" ? Buffer.from(data, "utf8") : Buffer.from(data);
  const parsed = parseStrictJson(raw);
  if (!raw.equals(canonicalJsonBytes(parsed))) {
    throw new SyntaxError("JSON bytes are not RFC 8785 canonical");
  }
  return parsed;
}

export function sha256(data: Uint8Array): string {
  return `sha256:${createHash("sha256").update(data).digest("hex")}`;
}

export function canonicalJsonHash(value: unknown): string {
  return sha256(canonicalJsonBytes(value));
}

export function computeSceneRevision(scene: Record<string, unknown>): string {
  const { revision: _revision, ...draft } = scene;
  return canonicalJsonHash(draft);
}

export function withSceneRevision(scene: Record<string, unknown>): Record<string, unknown> {
  const result = structuredClone(scene);
  result.revision = computeSceneRevision(result);
  return result;
}
