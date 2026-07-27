import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { Ajv2020 } from "ajv/dist/2020.js";
import { parseStrictJson } from "./canonical.js";

export type ValidationPhase = "parse" | "structure" | "semantic" | "package" | "budget";
export type ValidationArtifact = "scene" | "entities" | "presentation" | "connector_binding" | "normalized_product" | "package" | "glb" | "zip";

export interface ValidationRule {
  readonly id: string;
  readonly phase: ValidationPhase;
  readonly precedence: number;
  readonly artifacts: readonly ValidationArtifact[];
  readonly pointer_policy: "exact" | "nearest_record" | "root";
  readonly summary: string;
}

interface ValidationRuleRegistry {
  readonly schema_version: "1.0";
  readonly registry_id: "scene-1.0-rules";
  readonly phases: readonly ValidationPhase[];
  readonly rules: readonly ValidationRule[];
}

export interface ValidationIssue {
  severity: "error";
  code: string;
  path: string;
  message: string;
  phase: ValidationPhase;
}

export interface ValidationReport {
  valid: boolean;
  issues: readonly ValidationIssue[];
  firstError: ValidationIssue | null;
}

const phaseOrder: Record<ValidationPhase, number> = {
  parse: 0,
  structure: 1,
  semantic: 2,
  package: 3,
  budget: 4,
};

function utf8Compare(left: string, right: string): number {
  return Buffer.compare(Buffer.from(left, "utf8"), Buffer.from(right, "utf8"));
}

const contractRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "../../../src/simplecadapi/scene/contracts",
);
const ruleSchema = parseStrictJson(readFileSync(resolve(contractRoot, "schemas/rules-1.schema.json")));
const validateRuleSchema = new Ajv2020({ strict: true, allErrors: true }).compile(ruleSchema as object);

export function validateRuleRegistry(value: unknown): ReadonlyMap<string, ValidationRule> {
  if (!validateRuleSchema(value)) {
    const errors = [...(validateRuleSchema.errors ?? [])].sort(
      (left, right) => utf8Compare(left.instancePath, right.instancePath) ||
        utf8Compare(left.message ?? "", right.message ?? ""),
    );
    const first = errors[0];
    throw new Error(`invalid scene rule registry at ${first?.instancePath ?? ""}: ${first?.message ?? "schema validation failed"}`);
  }

  const registry = value as ValidationRuleRegistry;
  const registryPhaseOrder = new Map(registry.phases.map((phase, index) => [phase, index]));
  const byId = new Map<string, ValidationRule>();
  const phasePrecedence = new Set<string>();
  for (const rule of registry.rules) {
    if (byId.has(rule.id)) throw new Error(`invalid scene rule registry: duplicate rule ID ${JSON.stringify(rule.id)}`);
    const precedenceKey = `${rule.phase}\0${rule.precedence}`;
    if (phasePrecedence.has(precedenceKey)) {
      throw new Error(`invalid scene rule registry: duplicate precedence ${rule.precedence} in phase ${JSON.stringify(rule.phase)}`);
    }
    byId.set(rule.id, rule);
    phasePrecedence.add(precedenceKey);
  }
  const expected = [...registry.rules].sort(
    (left, right) =>
      registryPhaseOrder.get(left.phase)! - registryPhaseOrder.get(right.phase)! ||
      left.precedence - right.precedence,
  );
  if (registry.rules.some((rule, index) => rule !== expected[index])) {
    throw new Error("invalid scene rule registry: rules must be ordered by phase and precedence");
  }
  for (const phase of registry.phases) {
    const phaseRules = registry.rules.filter((rule) => rule.phase === phase);
    const ids = phaseRules.map((rule) => rule.id);
    const expectedIds = [...ids].sort(utf8Compare);
    if (ids.some((id, index) => id !== expectedIds[index])) {
      throw new Error(`invalid scene rule registry: precedence in phase ${JSON.stringify(phase)} must match unsigned UTF-8 rule-ID order`);
    }
  }
  return byId;
}

const rules = validateRuleRegistry(
  parseStrictJson(readFileSync(resolve(contractRoot, "rules/scene-1.0-rules.json"))),
);

export function hasRootPointerPolicy(code: string): boolean {
  return rules.get(code)?.pointer_policy === "root";
}

export function issue(
  code: string,
  path: string,
  message: string,
  phase: ValidationPhase = "semantic",
): ValidationIssue {
  return { severity: "error", code, path, message, phase };
}

export function report(input: Iterable<ValidationIssue>, artifact?: ValidationArtifact): ValidationReport {
  const unique = new Map<string, ValidationIssue>();
  for (const item of input) {
    if (artifact !== undefined) {
      const rule = rules.get(item.code);
      if (rule === undefined) throw new Error(`unregistered scene validation issue code: ${JSON.stringify(item.code)}`);
      if (item.phase !== rule.phase) {
        throw new Error(`scene validation issue ${JSON.stringify(item.code)} has phase ${JSON.stringify(item.phase)}; registered phase is ${JSON.stringify(rule.phase)}`);
      }
      if (!rule.artifacts.includes(artifact)) {
        throw new Error(`scene validation issue ${JSON.stringify(item.code)} does not apply to artifact ${JSON.stringify(artifact)}`);
      }
      if (rule.pointer_policy === "root" && item.path !== "") {
        throw new Error(`scene validation issue ${JSON.stringify(item.code)} requires the root pointer`);
      }
    }
    const key = artifact === undefined
      ? `${item.phase}\0${item.code}\0${item.path}`
      : `${item.phase}\0${item.code}\0${item.path}\0${item.message}`;
    if (!unique.has(key)) unique.set(key, item);
  }
  const issues = [...unique.values()].sort(
    (left, right) =>
      phaseOrder[left.phase] - phaseOrder[right.phase] ||
      (artifact === undefined
        ? utf8Compare(left.code, right.code)
        : rules.get(left.code)!.precedence - rules.get(right.code)!.precedence) ||
      utf8Compare(left.path, right.path) ||
      utf8Compare(left.message, right.message),
  );
  return { valid: issues.length === 0, issues, firstError: issues[0] ?? null };
}

export function pointer(parts: readonly (string | number)[]): string {
  if (parts.length === 0) return "";
  return `/${parts.map((part) => String(part).replaceAll("~", "~0").replaceAll("/", "~1")).join("/")}`;
}
