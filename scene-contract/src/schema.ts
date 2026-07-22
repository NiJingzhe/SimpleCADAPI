import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Ajv2020, type ErrorObject, type ValidateFunction } from "ajv/dist/2020.js";
import { parseStrictJson } from "./canonical.js";

const contractRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../src/simplecadapi/scene/contracts/schemas",
);

const ajv = new Ajv2020({ strict: true, allErrors: true });

function declareRequiredProperties(value: unknown): void {
  if (value === null || typeof value !== "object") return;
  const schema = value as Record<string, unknown>;
  if (
    schema.type === undefined &&
    (schema.properties !== undefined || schema.required !== undefined)
  ) {
    schema.type = "object";
  }
  if (Array.isArray(schema.required) && schema.required.every((item) => typeof item === "string")) {
    const properties =
      schema.properties !== null && typeof schema.properties === "object" && !Array.isArray(schema.properties)
        ? (schema.properties as Record<string, unknown>)
        : {};
    for (const name of schema.required) properties[name] ??= {};
    schema.properties = properties;
  }
  for (const key of ["properties", "$defs", "patternProperties", "dependentSchemas"]) {
    const schemas = schema[key];
    if (schemas !== null && typeof schemas === "object" && !Array.isArray(schemas)) {
      Object.values(schemas).forEach(declareRequiredProperties);
    }
  }
  for (const key of ["allOf", "anyOf", "oneOf", "prefixItems"]) {
    const schemas = schema[key];
    if (Array.isArray(schemas)) schemas.forEach(declareRequiredProperties);
  }
  for (const key of [
    "not",
    "if",
    "then",
    "else",
    "items",
    "contains",
    "additionalProperties",
    "unevaluatedProperties",
    "propertyNames",
  ]) {
    declareRequiredProperties(schema[key]);
  }
}

function load(name: string): ValidateFunction {
  const schema = parseStrictJson(readFileSync(resolve(contractRoot, name)));
  // Ajv strictRequired expects declarations in the same nested subschema. The
  // contract uses valid required-only guards, so add behavior-neutral schemas.
  declareRequiredProperties(schema);
  return ajv.compile(schema as object);
}

export type SchemaArtifact = "scene" | "entities" | "presentation" | "connector_binding" | "normalized_product";

const schemaFiles: Record<SchemaArtifact, string> = {
  scene: "scene-1.0.schema.json",
  entities: "entities-1.0.schema.json",
  presentation: "presentation-1.0.schema.json",
  connector_binding: "connector-binding-1.0.schema.json",
  normalized_product: "normalized-product-1.schema.json",
};
const schemaDocuments = Object.fromEntries(
  Object.entries(schemaFiles).map(([artifact, name]) => [artifact, parseStrictJson(readFileSync(resolve(contractRoot, name)))]),
) as Record<SchemaArtifact, Record<string, unknown>>;
const pointerValidators = new Map<string, ValidateFunction>();

export function validateSchemaPointer(artifact: SchemaArtifact, schemaPointer: string, value: unknown): boolean {
  const key = `${artifact}:${schemaPointer}`;
  let validate = pointerValidators.get(key);
  if (validate === undefined) {
    const root = structuredClone(schemaDocuments[artifact]);
    delete root.$id;
    const wrapper = schemaPointer === "#"
      ? root
      : { $schema: root.$schema, $ref: schemaPointer, $defs: root.$defs };
    declareRequiredProperties(wrapper);
    validate = ajv.compile(wrapper);
    pointerValidators.set(key, validate);
  }
  return Boolean(validate(value));
}

export const validateSceneSchema = load("scene-1.0.schema.json");
export const validateEntitiesSchema = load("entities-1.0.schema.json");
export const validatePresentationSchema = load("presentation-1.0.schema.json");
export const validateConnectorBindingSchema = load("connector-binding-1.0.schema.json");
export const validateNormalizedProductSchema = load("normalized-product-1.schema.json");

export function schemaErrors(validate: ValidateFunction, value: unknown): ErrorObject[] {
  validate(value);
  return validate.errors === null || validate.errors === undefined ? [] : [...validate.errors];
}
