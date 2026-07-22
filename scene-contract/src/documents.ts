import type {
  ConnectorBindingDocument as ConnectorBindingValue,
  EntityDocument as EntityValue,
  NormalizedProductDocument as NormalizedProductValue,
  PresentationDocument as PresentationValue,
  SceneDocument as SceneValue,
} from "./generated/index.js";
import { canonicalJsonBytes, parseCanonicalJson, sha256 } from "./canonical.js";
import type { ValidationReport } from "./report.js";
import {
  validateConnectorBinding,
  validateEntityAsset,
  validateNormalizedProduct,
  validatePresentation,
  validateSceneManifest,
} from "./validation.js";

export type SceneDocument = SceneValue;
export type EntityDocument = EntityValue;
export type PresentationDocument = PresentationValue;
export type ConnectorBindingDocument = ConnectorBindingValue;
export type NormalizedProductDocument = NormalizedProductValue;

export type DeepReadonly<T> =
  T extends (...args: never[]) => unknown
    ? T
    : T extends readonly (infer Item)[]
      ? readonly DeepReadonly<Item>[]
      : T extends object
        ? { readonly [Key in keyof T]: DeepReadonly<T[Key]> }
        : T;

export interface ImmutableContractDocument<Value> {
  readonly value: DeepReadonly<Value>;
  readonly canonicalBytes: Buffer;
  readonly canonicalHash: string;
  toMutable(): Value;
}

export interface ImmutableSceneDocument
  extends ImmutableContractDocument<SceneValue> {
  readonly revision: string;
}

export type ImmutableEntityDocument = ImmutableContractDocument<EntityValue>;
export type ImmutablePresentationDocument =
  ImmutableContractDocument<PresentationValue>;
export type ImmutableConnectorBindingDocument =
  ImmutableContractDocument<ConnectorBindingValue>;
export type ImmutableNormalizedProductDocument =
  ImmutableContractDocument<NormalizedProductValue>;

export interface ContractDocumentFactory<Value, Document> {
  fromValue(value: Value | DeepReadonly<Value>): Document;
  parse(data: Uint8Array | string): Document;
}

export class ContractDocumentValidationError extends TypeError {
  public constructor(public readonly report: ValidationReport) {
    const first = report.firstError;
    super(
      first === null
        ? "Scene contract validation failed"
        : `Scene contract validation failed: ${first.code} at ${first.path}: ${first.message}`,
    );
    this.name = "ContractDocumentValidationError";
  }
}

type Validator = (value: unknown) => ValidationReport;

function deepFreeze(value: unknown): unknown {
  if (Array.isArray(value)) {
    for (const child of value) deepFreeze(child);
    return Object.freeze(value);
  }
  if (value !== null && typeof value === "object") {
    for (const child of Object.values(value)) deepFreeze(child);
    return Object.freeze(value);
  }
  return value;
}

class FrozenContractDocument<Value>
  implements ImmutableContractDocument<Value>
{
  readonly #value: DeepReadonly<Value>;
  readonly #canonicalBytes: Buffer;
  readonly #canonicalHash: string;

  public constructor(value: Value | DeepReadonly<Value>, validate: Validator) {
    const canonical = canonicalJsonBytes(value);
    const detached = parseCanonicalJson(canonical);
    const validation = validate(detached);
    if (!validation.valid) throw new ContractDocumentValidationError(validation);
    this.#value = deepFreeze(detached) as DeepReadonly<Value>;
    this.#canonicalBytes = Buffer.from(canonical);
    this.#canonicalHash = sha256(canonical);
    Object.freeze(this);
  }

  public get value(): DeepReadonly<Value> {
    return this.#value;
  }

  public get canonicalBytes(): Buffer {
    return Buffer.from(this.#canonicalBytes);
  }

  public get canonicalHash(): string {
    return this.#canonicalHash;
  }

  public toMutable(): Value {
    return parseCanonicalJson(this.#canonicalBytes) as Value;
  }
}

class FrozenSceneDocument
  extends FrozenContractDocument<SceneValue>
  implements ImmutableSceneDocument
{
  public get revision(): string {
    return this.value.revision;
  }
}

function documentFactory<Value, Document>(
  create: (value: Value | DeepReadonly<Value>) => Document,
): ContractDocumentFactory<Value, Document> {
  return Object.freeze({
    fromValue: create,
    parse: (data: Uint8Array | string) => create(parseCanonicalJson(data) as Value),
  });
}

export const SceneDocument = documentFactory<SceneValue, ImmutableSceneDocument>(
  (value) => new FrozenSceneDocument(value, validateSceneManifest),
);

export const EntityDocument = documentFactory<EntityValue, ImmutableEntityDocument>(
  (value) => new FrozenContractDocument<EntityValue>(value, validateEntityAsset),
);

export const PresentationDocument = documentFactory<
  PresentationValue,
  ImmutablePresentationDocument
>((value) => new FrozenContractDocument<PresentationValue>(value, validatePresentation));

export const ConnectorBindingDocument = documentFactory<
  ConnectorBindingValue,
  ImmutableConnectorBindingDocument
>((value) => new FrozenContractDocument<ConnectorBindingValue>(value, validateConnectorBinding));

export const NormalizedProductDocument = documentFactory<
  NormalizedProductValue,
  ImmutableNormalizedProductDocument
>((value) => new FrozenContractDocument<NormalizedProductValue>(value, validateNormalizedProduct));
