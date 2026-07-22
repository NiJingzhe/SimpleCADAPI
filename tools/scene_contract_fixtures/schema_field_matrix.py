"""Schema-grounded structural field matrices for all contract artifacts."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from jsonschema import Draft202012Validator


Json = Any


SCHEMAS = {
    "scene": "scene-1.0.schema.json",
    "entities": "entities-1.0.schema.json",
    "presentation": "presentation-1.0.schema.json",
    "connector_binding": "connector-binding-1.0.schema.json",
    "normalized_product": "normalized-product-1.schema.json",
}


def _resolve(root: Mapping[str, Any], schema: Mapping[str, Any]) -> Mapping[str, Any]:
    reference = schema.get("$ref")
    if not isinstance(reference, str) or not reference.startswith("#/"):
        return schema
    current: Any = root
    for part in reference[2:].split("/"):
        current = current[part.replace("~1", "/").replace("~0", "~")]
    return current


def _wrapper(root: Mapping[str, Any], pointer: str) -> dict[str, Any]:
    if pointer == "#":
        return deepcopy(dict(root))
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$ref": pointer,
        "$defs": deepcopy(root.get("$defs", {})),
    }


def _string_example(schema: Mapping[str, Any]) -> str:
    pattern = str(schema.get("pattern", ""))
    if pattern == "^sha256:[0-9a-f]{64}$":
        return "sha256:" + "0" * 64
    if pattern.startswith("^appearance/evaluated/"):
        return "appearance/evaluated/" + "0" * 64
    if pattern.startswith("^entity/"):
        return "entity/face/0"
    for candidate in ("a", "x", "root", "entity/face/0"):
        if not pattern or re.fullmatch(pattern, candidate):
            return candidate
    raise AssertionError(f"no structural string example for pattern {pattern!r}")


def _accepts_null(root: Mapping[str, Any], schema: Mapping[str, Any]) -> bool:
    wrapper = deepcopy(dict(schema))
    wrapper["$defs"] = deepcopy(root.get("$defs", {}))
    return Draft202012Validator(wrapper).is_valid(None)


def _nonnull_example(root: Mapping[str, Any], schema: Mapping[str, Any]) -> Json:
    resolved = _resolve(root, schema)
    if "oneOf" in resolved:
        for branch in resolved["oneOf"]:
            if not _accepts_null(root, branch):
                return _example(root, branch, prefer_nonnull=True)
    types = resolved.get("type")
    if isinstance(types, list):
        draft = dict(resolved)
        draft["type"] = next(item for item in types if item != "null")
        return _example(root, draft, prefer_nonnull=True)
    return _example(root, resolved, prefer_nonnull=True)


def _condition_matches(
    root: Mapping[str, Any], condition: Mapping[str, Any], value: Json
) -> bool:
    schema = deepcopy(dict(condition))
    schema["$defs"] = deepcopy(root.get("$defs", {}))
    return Draft202012Validator(schema).is_valid(value)


def _example(
    root: Mapping[str, Any],
    schema: Mapping[str, Any],
    *,
    overrides: Mapping[str, Json] | None = None,
    prefer_nonnull: bool = False,
) -> Json:
    resolved = _resolve(root, schema)
    if "const" in resolved:
        return deepcopy(resolved["const"])
    if "enum" in resolved:
        return deepcopy(resolved["enum"][0])
    for union_key in ("oneOf", "anyOf"):
        if union_key in resolved and not (
            resolved.get("type") == "object" or "properties" in resolved
        ):
            branches = resolved[union_key]
            if prefer_nonnull:
                branches = sorted(
                    branches,
                    key=lambda branch: _accepts_null(root, branch),
                )
            return _example(root, branches[0], prefer_nonnull=prefer_nonnull)
    types = resolved.get("type")
    if isinstance(types, list):
        if "null" in types and not prefer_nonnull:
            return None
        types = next(item for item in types if item != "null")
    if types == "object" or "properties" in resolved:
        properties = resolved.get("properties", {})
        result = {
            field: _example(root, properties.get(field, {}))
            for field in resolved.get("required", [])
        }
        if overrides:
            result.update(deepcopy(dict(overrides)))
        for branch in resolved.get("anyOf", []):
            branch_required = branch.get("required", [])
            if branch_required:
                for field in branch_required:
                    result.setdefault(field, _example(root, properties.get(field, {})))
                break
        for condition in resolved.get("allOf", []):
            then = condition.get("then")
            if isinstance(then, dict) and _condition_matches(
                root, condition.get("if", {}), result
            ):
                for field in then.get("required", []):
                    result.setdefault(field, _example(root, properties.get(field, {})))
        return result
    if types == "array" or "prefixItems" in resolved:
        result = [_example(root, item) for item in resolved.get("prefixItems", [])]
        minimum = resolved.get("minItems", 0)
        while len(result) < minimum:
            result.append(_example(root, resolved.get("items", {})))
        return result
    if types == "string":
        return _string_example(resolved)
    if types == "integer":
        return int(resolved.get("minimum", 0))
    if types == "number":
        if "exclusiveMinimum" in resolved:
            return resolved["exclusiveMinimum"] + 1
        return resolved.get("minimum", 0)
    if types == "boolean":
        return False
    if types == "null":
        return None
    return {}


def _closed_records(schema: Mapping[str, Any]) -> list[tuple[str, Mapping[str, Any]]]:
    result: dict[str, Mapping[str, Any]] = {}
    if schema.get("type") == "object" and schema.get("additionalProperties") is False:
        result["#"] = schema

    def visit(value: Any, pointer: str) -> None:
        if not isinstance(value, dict):
            return
        if value.get("type") == "object" and value.get("additionalProperties") is False:
            result[pointer] = value
        for key in ("properties", "items", "oneOf", "anyOf", "allOf"):
            child = value.get(key)
            if isinstance(child, dict):
                for name, nested in child.items():
                    visit(nested, f"{pointer}/{key}/{name}")
            elif isinstance(child, list):
                for index, nested in enumerate(child):
                    visit(nested, f"{pointer}/{key}/{index}")

    for name, definition in schema.get("$defs", {}).items():
        visit(definition, f"#/$defs/{name}")
    return list(result.items())


def _mutate(base: Json, operation: str, field: str, value: Json = None) -> Json:
    result = deepcopy(base)
    if operation == "delete":
        del result[field]
    else:
        result[field] = deepcopy(value)
    return result


def _record_matrix(
    artifact: str,
    root: Mapping[str, Any],
    pointer: str,
    schema: Mapping[str, Any],
    *,
    overrides: Mapping[str, Json] | None = None,
    variant: str = "base",
) -> dict[str, Any]:
    validator = Draft202012Validator(_wrapper(root, pointer))
    base = _example(root, schema, overrides=overrides)
    if not validator.is_valid(base):
        errors = [error.message for error in validator.iter_errors(base)]
        raise AssertionError(
            f"invalid generated {artifact} {pointer} {variant}: {errors}"
        )
    properties = schema.get("properties", {})
    cases: list[dict[str, Any]] = [
        {"mutations": [], "name": "base_valid", "valid": True}
    ]
    for field in base:
        cases.append(
            {
                "mutations": [{"operation": "delete", "path": [field]}],
                "name": f"missing_{field}",
                "valid": validator.is_valid(_mutate(base, "delete", field)),
            }
        )
    cases.append(
        {
            "mutations": [
                {"operation": "set", "path": ["unknown"], "value": True}
            ],
            "name": "unknown_field",
            "valid": validator.is_valid(_mutate(base, "set", "unknown", True)),
        }
    )
    optional = [field for field in properties if field not in base]
    for field in optional:
        present = _example(root, properties[field])
        cases.append(
            {
                "mutations": [
                    {"operation": "set", "path": [field], "value": present}
                ],
                "name": f"optional_{field}_present",
                "valid": validator.is_valid(_mutate(base, "set", field, present)),
            }
        )
    if optional:
        all_present = deepcopy(base)
        mutations = []
        for field in optional:
            present = _example(root, properties[field])
            all_present[field] = present
            mutations.append(
                {"operation": "set", "path": [field], "value": present}
            )
        cases.append(
            {
                "mutations": mutations,
                "name": "optional_fields_all_present",
                "valid": validator.is_valid(all_present),
            }
        )
    for field, field_schema in properties.items():
        if field in base and base[field] is None and _accepts_null(root, field_schema):
            nonnull = _nonnull_example(root, field_schema)
            cases.append(
                {
                    "mutations": [
                        {"operation": "set", "path": [field], "value": nonnull}
                    ],
                    "name": f"nullable_{field}_nonnull",
                    "valid": validator.is_valid(
                        _mutate(base, "set", field, nonnull)
                    ),
                }
            )
    return {
        "artifact": artifact,
        "base": base,
        "cases": cases,
        "schema_pointer": pointer,
        "variant": variant,
    }


def build_schema_field_matrices(schema_dir: Path) -> list[dict[str, Any]]:
    """Build declarative matrices for every closed object and discriminator."""

    matrices: list[dict[str, Any]] = []
    for artifact, filename in SCHEMAS.items():
        root = json.loads(schema_dir.joinpath(filename).read_text(encoding="utf-8"))
        for pointer, schema in _closed_records(root):
            discriminator = next(
                (
                    (field, field_schema["enum"])
                    for field, field_schema in schema.get("properties", {}).items()
                    if isinstance(field_schema, dict)
                    and len(field_schema.get("enum", [])) > 1
                ),
                None,
            )
            variants: list[tuple[str, Mapping[str, Json] | None]] = [("base", None)]
            if discriminator is not None:
                field, values = discriminator
                variants = [
                    (f"{field}={value}", {field: value}) for value in values
                ]
            if artifact == "normalized_product" and pointer == "#/$defs/connector":
                variants = []
                for anchor_name in (
                    "geometryAnchor",
                    "placementAnchor",
                    "forwardedAnchor",
                ):
                    anchor = _example(root, root["$defs"][anchor_name])
                    variants.append(
                        (f"anchor={anchor['anchor_kind']}", {"anchor": anchor})
                    )
            for variant, overrides in variants:
                matrices.append(
                    _record_matrix(
                        artifact,
                        root,
                        pointer,
                        schema,
                        overrides=overrides,
                        variant=variant,
                    )
                )
    identities = [
        (matrix["artifact"], matrix["schema_pointer"], matrix["variant"])
        for matrix in matrices
    ]
    if len(identities) != len(set(identities)):
        raise AssertionError("duplicate schema field matrix identity")
    return matrices
