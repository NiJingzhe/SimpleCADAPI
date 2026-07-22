"""Structural and semantic validators for the proposed Scene 1.0 contract."""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib.resources import files
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Sequence
from urllib.parse import quote

from jsonschema import Draft202012Validator

from .canonical import (
    DuplicateKeyError,
    canonical_json_bytes,
    canonical_json_hash,
    compute_scene_revision,
    parse_canonical_json,
    parse_strict_json,
)
from .glb import GlbInfo, preflight_glb
from .resources import BASE_LIMITS, SceneResourceLimits, preflight_resource_count
from .transforms import compose_rigid_transforms, rigid_transforms_equal


SCHEMA_FILES = {
    "scene": "schemas/scene-1.0.schema.json",
    "entities": "schemas/entities-1.0.schema.json",
    "presentation": "schemas/presentation-1.0.schema.json",
    "connector_binding": "schemas/connector-binding-1.0.schema.json",
    "normalized_product": "schemas/normalized-product-1.schema.json",
}

_PHASE_ORDER = {"parse": 0, "structure": 1, "semantic": 2, "package": 3, "budget": 4}
_SET_ARRAY_KEYS = {"semantic_binding_ids", "evaluated_tags", "parent_entity_ids", "child_entity_ids"}
_IDENTIFIER_ARRAY_KEYS = {
    "child_entity_ids",
    "component_path",
    "evaluated_tags",
    "grounded_component_ids",
    "parent_entity_ids",
    "semantic_binding_ids",
}
_COLLECTION_SORT_KEYS = {
    "definitions": "definition_id",
    "nodes": "node_id",
    "geometry_assets": "asset_id",
    "edge_assets": "asset_id",
    "entity_assets": "entity_asset_id",
    "appearances": "appearance_id",
    "connectors": "connector_snapshot_id",
    "cameras": "camera_id",
    "entities": "entity_id",
}
_RULE_SCHEMA_PATH = "schemas/rules-1.schema.json"
_RULE_REGISTRY_PATH = "rules/scene-1.0-rules.json"
_SOURCE_PATH_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]*\.py$")
_SOURCE_KEYS = {
    "schema_version",
    "path",
    "path_kind",
    "line",
    "column",
    "end_line",
    "end_column",
    "call_text",
    "callsite_id",
    "assignment_targets",
}


@dataclass(frozen=True)
class SceneValidationIssue:
    severity: str
    code: str
    path: str
    message: str
    phase: str

    def to_dict(self) -> dict[str, str]:
        return {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }


@dataclass(frozen=True)
class SceneValidationReport:
    issues: tuple[SceneValidationIssue, ...] = ()

    @property
    def valid(self) -> bool:
        return not self.issues

    @property
    def first_error(self) -> SceneValidationIssue | None:
        return self.issues[0] if self.issues else None

    def to_dict(self) -> dict[str, Any]:
        return {"valid": self.valid, "issues": [issue.to_dict() for issue in self.issues]}


class SceneContractError(ValueError):
    """Raised by assert helpers with the complete deterministic report."""

    def __init__(self, report: SceneValidationReport) -> None:
        self.report = report
        first = report.first_error
        message = "Scene contract validation failed"
        if first is not None:
            message += f": {first.code} at {first.path}: {first.message}"
        super().__init__(message)


def _pointer(parts: Iterable[Any]) -> str:
    encoded = [str(part).replace("~", "~0").replace("/", "~1") for part in parts]
    return "/" + "/".join(encoded) if encoded else ""


def _join_pointer(prefix: str, *parts: Any) -> str:
    suffix = _pointer(parts)
    return prefix + suffix if prefix else suffix


def _utf8_key(value: str) -> bytes:
    return value.encode("utf-8")


def _issue(code: str, path: str, message: str, phase: str = "semantic") -> SceneValidationIssue:
    return SceneValidationIssue("error", code, path, message, phase)


def _validate_rule_registry(
    registry: Any, schema: Any
) -> dict[str, Mapping[str, Any]]:
    """Validate registry shape and the ordering invariants JSON Schema cannot express."""

    Draft202012Validator.check_schema(schema)
    errors = sorted(
        Draft202012Validator(schema).iter_errors(registry),
        key=lambda error: (_pointer(error.absolute_path).encode("utf-8"), error.message),
    )
    if errors:
        first = errors[0]
        raise ValueError(
            f"invalid scene rule registry at {_pointer(first.absolute_path)}: {first.message}"
        )

    phases = registry["phases"]
    phase_order = {phase: index for index, phase in enumerate(phases)}
    rules = registry["rules"]
    by_id: dict[str, Mapping[str, Any]] = {}
    phase_precedence: set[tuple[str, int]] = set()
    for rule in rules:
        rule_id = rule["id"]
        if rule_id in by_id:
            raise ValueError(f"invalid scene rule registry: duplicate rule ID {rule_id!r}")
        key = (rule["phase"], rule["precedence"])
        if key in phase_precedence:
            raise ValueError(
                "invalid scene rule registry: duplicate precedence "
                f"{rule['precedence']} in phase {rule['phase']!r}"
            )
        by_id[rule_id] = rule
        phase_precedence.add(key)

    expected = sorted(
        rules,
        key=lambda rule: (phase_order[rule["phase"]], rule["precedence"]),
    )
    if rules != expected:
        raise ValueError(
            "invalid scene rule registry: rules must be ordered by phase and precedence"
        )
    for phase in phases:
        phase_rules = [rule for rule in rules if rule["phase"] == phase]
        precedence_ids = [rule["id"] for rule in phase_rules]
        utf8_ids = sorted(precedence_ids, key=_utf8_key)
        if precedence_ids != utf8_ids:
            raise ValueError(
                "invalid scene rule registry: precedence in phase "
                f"{phase!r} must match unsigned UTF-8 rule-ID order"
            )
    return by_id


@lru_cache(maxsize=1)
def _rule_registry() -> dict[str, Mapping[str, Any]]:
    schema = _load_json_artifact(_RULE_SCHEMA_PATH)
    registry = _load_json_artifact(_RULE_REGISTRY_PATH)
    return _validate_rule_registry(registry, schema)


def _has_root_pointer_policy(code: str) -> bool:
    rule = _rule_registry().get(code)
    return rule is not None and rule["pointer_policy"] == "root"


def _report(
    issues: Iterable[SceneValidationIssue], *, artifact: str | None = None
) -> SceneValidationReport:
    rules = _rule_registry()
    unique: dict[tuple[str, ...], SceneValidationIssue] = {}
    for issue in issues:
        if artifact is not None:
            rule = rules.get(issue.code)
            if rule is None:
                raise ValueError(f"unregistered scene validation issue code: {issue.code!r}")
            if issue.phase != rule["phase"]:
                raise ValueError(
                    f"scene validation issue {issue.code!r} has phase {issue.phase!r}; "
                    f"registered phase is {rule['phase']!r}"
                )
            if artifact not in rule["artifacts"]:
                raise ValueError(
                    f"scene validation issue {issue.code!r} does not apply to artifact {artifact!r}"
                )
            if rule["pointer_policy"] == "root" and issue.path != "":
                raise ValueError(
                    f"scene validation issue {issue.code!r} requires the root pointer"
                )
        key = (
            (issue.phase, issue.code, issue.path)
            if artifact is None
            else (issue.phase, issue.code, issue.path, issue.message)
        )
        unique.setdefault(key, issue)
    ordered = sorted(
        unique.values(),
        key=lambda issue: (
            _PHASE_ORDER[issue.phase],
            rules[issue.code]["precedence"] if artifact is not None else issue.code.encode("utf-8"),
            issue.path.encode("utf-8"),
            issue.message.encode("utf-8"),
        ),
    )
    return SceneValidationReport(tuple(ordered))


def _has_blocking_issues(issues: Iterable[SceneValidationIssue]) -> bool:
    return any(issue.phase in {"parse", "structure"} for issue in issues)


def _has_unsafe_depth(issues: Iterable[SceneValidationIssue]) -> bool:
    return any(
        issue.code == "resource_limit_exceeded" and "nesting" in issue.message
        for issue in issues
    )


def _serialized_size(value: Any) -> int | None:
    if isinstance(value, str):
        try:
            return len(value.encode("utf-8"))
        except UnicodeEncodeError:
            return None
    if isinstance(value, memoryview):
        return value.nbytes
    if isinstance(value, (bytes, bytearray)):
        return len(value)
    try:
        return len(canonical_json_bytes(value))
    except (RecursionError, TypeError, ValueError, UnicodeEncodeError):
        return None


def _serialized_size_issues(
    value: Any,
    artifact: str,
    *,
    limits: SceneResourceLimits,
) -> list[SceneValidationIssue]:
    size = _serialized_size(value)
    limit = {
        "scene": limits.scene_json_bytes,
        "entities": limits.entity_json_bytes,
        "presentation": limits.presentation_json_bytes,
    }.get(artifact, limits.one_member_bytes)
    if size is None or size <= limit:
        return []
    return [
        _issue(
            "resource_limit_exceeded",
            "",
            f"{artifact} JSON bytes exceed resource limit",
            "budget",
        )
    ]


def _contract_root():
    return files("simplecadapi.scene").joinpath("contracts")


def load_contract_artifact(relative_path: str) -> bytes:
    """Load exact packaged contract bytes by a safe package-relative path."""

    if relative_path.startswith("/") or ".." in relative_path.split("/"):
        raise ValueError("contract artifact path must remain package-relative")
    return _contract_root().joinpath(*relative_path.split("/")).read_bytes()


@lru_cache(maxsize=None)
def _load_json_artifact(relative_path: str) -> Any:
    return parse_strict_json(load_contract_artifact(relative_path))


@lru_cache(maxsize=None)
def _validator(artifact: str) -> Draft202012Validator:
    schema = _load_json_artifact(SCHEMA_FILES[artifact])
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _schema_issues(value: Any, artifact: str) -> list[SceneValidationIssue]:
    issues: list[SceneValidationIssue] = []
    for error in _validator(artifact).iter_errors(value):
        path = _pointer(error.absolute_path)
        if error.validator == "additionalProperties":
            # jsonschema points to the containing object; this remains stable
            # across Python and TypeScript validators.
            message = "unknown field is forbidden by the closed schema"
        else:
            message = error.message
        issues.append(_issue("schema_invalid", path, message, "structure"))
    return issues


def _parse_input(value: Any, *, require_canonical: bool) -> tuple[Any | None, list[SceneValidationIssue]]:
    if isinstance(value, MappingProxyType):
        return _thaw_frozen_json(value), []
    if not isinstance(value, (bytes, bytearray, memoryview, str)):
        return value, []
    try:
        parsed = parse_canonical_json(value) if require_canonical else parse_strict_json(value)
        return parsed, []
    except DuplicateKeyError as exc:
        return None, [_issue("duplicate_json_key", "", str(exc), "parse")]
    except UnicodeDecodeError as exc:
        return None, [_issue("invalid_utf8", "", str(exc), "parse")]
    except ValueError as exc:
        message = str(exc)
        if "BOM" in message:
            code = "bom_forbidden"
        elif "surrogate" in message:
            code = "invalid_utf8"
        elif "finite" in message or "NaN" in message or "Infinity" in message:
            code = "nonfinite_json_number"
        elif require_canonical and "canonical" in message:
            code = "noncanonical_json"
        elif "nesting" in message:
            code = "resource_limit_exceeded"
        else:
            code = "schema_invalid"
        phase = "budget" if code == "resource_limit_exceeded" else "parse" if code != "schema_invalid" else "structure"
        return None, [_issue(code, "", message, phase)]


def _thaw_frozen_json(value: Any) -> Any:
    """Convert the immutable package view without recursing through user JSON."""

    result: dict[int, Any] = {}
    stack: list[tuple[Any, int | None, Any]] = [(value, None, None)]
    root: Any = None
    while stack:
        current, parent_id, parent_key = stack.pop()
        if isinstance(current, Mapping):
            target: dict[str, Any] = {}
            if parent_id is None:
                root = target
            else:
                result[parent_id][parent_key] = target
            result[id(current)] = target
            for key, child in reversed(tuple(current.items())):
                stack.append((child, id(current), key))
        elif isinstance(current, tuple):
            target_list: list[Any] = [None] * len(current)
            if parent_id is None:
                root = target_list
            else:
                result[parent_id][parent_key] = target_list
            result[id(current)] = target_list
            for index in range(len(current) - 1, -1, -1):
                stack.append((current[index], id(current), index))
        elif parent_id is None:
            root = current
        else:
            result[parent_id][parent_key] = current
    return root


def _walk_json(value: Any, path: tuple[Any, ...] = ()) -> Iterable[tuple[tuple[Any, ...], Any]]:
    stack = [(path, value)]
    while stack:
        current_path, current = stack.pop()
        yield current_path, current
        if isinstance(current, dict):
            stack.extend(
                ((*current_path, key), child)
                for key, child in reversed(tuple(current.items()))
            )
        elif isinstance(current, list):
            stack.extend(
                ((*current_path, index), child)
                for index, child in reversed(tuple(enumerate(current)))
            )


def _is_metadata_path(path: tuple[Any, ...]) -> bool:
    return any(part in {"metadata", "sdk_metadata"} for part in path)


def _is_identifier_path(path: tuple[Any, ...]) -> bool:
    if not path:
        return False
    field = path[-1]
    if isinstance(field, str) and (
        field.endswith("_id")
        or field in {"definition_ref", "source_element_id", "topo_id"}
    ):
        return True
    return (
        len(path) >= 2
        and isinstance(path[-2], str)
        and path[-2] in _IDENTIFIER_ARRAY_KEYS
        and isinstance(field, int)
    )


def _is_uri_path(path: tuple[Any, ...]) -> bool:
    return bool(path) and isinstance(path[-1], str) and (
        path[-1] == "uri" or path[-1].endswith("_uri")
    )


def _domain_issues(
    value: Any, *, limits: SceneResourceLimits = BASE_LIMITS
) -> list[SceneValidationIssue]:
    issues: list[SceneValidationIssue] = []
    for path, child in _walk_json(value):
        pointer = _pointer(path)
        if isinstance(child, dict):
            for key in child:
                if not isinstance(key, str):
                    issues.append(_issue("schema_invalid", pointer, "JSON object keys must be strings", "structure"))
                    continue
                try:
                    encoded_key = key.encode("utf-8")
                except UnicodeEncodeError:
                    issues.append(_issue("invalid_utf8", pointer, "object key contains an unpaired surrogate", "parse"))
                    continue
                key_pointer = _join_pointer(pointer, key)
                if len(encoded_key) > limits.json_string_bytes:
                    issues.append(_issue("resource_limit_exceeded", key_pointer, "JSON object key exceeds resource limit", "budget"))
                if _is_metadata_path(path) and len(encoded_key) > limits.structural_id_bytes:
                    issues.append(_issue("resource_limit_exceeded", key_pointer, "metadata key exceeds structural ID resource limit", "budget"))
        if isinstance(child, float) and not math.isfinite(child):
            issues.append(_issue("nonfinite_json_number", pointer, "JSON number must be finite", "parse"))
        if isinstance(child, int) and not isinstance(child, bool) and abs(child) > 9_007_199_254_740_991:
            issues.append(_issue("schema_invalid", pointer, "integer exceeds the JCS safe domain", "structure"))
        if isinstance(child, str):
            try:
                encoded = child.encode("utf-8")
            except UnicodeEncodeError:
                issues.append(_issue("invalid_utf8", pointer, "string contains an unpaired surrogate", "parse"))
                continue
            if len(encoded) > limits.json_string_bytes:
                issues.append(_issue("resource_limit_exceeded", pointer, "JSON string exceeds resource limit", "budget"))
            if _is_uri_path(path) and len(encoded) > limits.uri_bytes:
                issues.append(_issue("resource_limit_exceeded", pointer, "URI exceeds resource limit", "budget"))
            if _is_identifier_path(path) and len(encoded) > limits.structural_id_bytes:
                issues.append(_issue("resource_limit_exceeded", pointer, "identifier exceeds structural ID resource limit", "budget"))
        if len(path) > limits.json_depth:
            issues.append(_issue("resource_limit_exceeded", pointer, "JSON nesting exceeds resource limit", "budget"))
    return issues


def json_resource_issues(
    value: Any, *, limits: SceneResourceLimits = BASE_LIMITS
) -> tuple[SceneValidationIssue, ...]:
    """Return deterministic JSON-domain resource issues for boundary probes."""

    return _report(_domain_issues(value, limits=limits)).issues


def _resource_count_issues(
    value: Any,
    artifact: str,
    *,
    limits: SceneResourceLimits = BASE_LIMITS,
) -> list[SceneValidationIssue]:
    if not isinstance(value, dict):
        return []
    issues: list[SceneValidationIssue] = []
    collections: tuple[tuple[str, str], ...] = ()
    if artifact == "scene":
        collections = (
            ("definitions", "definitions"),
            ("nodes", "nodes"),
            ("geometry_assets", "assets_per_kind"),
            ("edge_assets", "assets_per_kind"),
            ("entity_assets", "assets_per_kind"),
            ("appearances", "appearances"),
            ("connectors", "connectors"),
            ("cameras", "cameras"),
        )
    elif artifact == "entities":
        collections = (
            ("entities", "entities_per_sidecar"),
            ("face_groups", "entities_per_sidecar"),
            ("edge_groups", "entities_per_sidecar"),
        )
    elif artifact == "presentation":
        collections = (
            ("node_overrides", "nodes"),
            ("appearances", "appearances"),
            ("cameras", "cameras"),
        )
    for field, limit_name in collections:
        records = value.get(field)
        if isinstance(records, list):
            try:
                preflight_resource_count(len(records), limit_name, limits=limits)
            except ValueError:
                issues.append(
                    _issue(
                        "resource_limit_exceeded",
                        f"/{field}",
                        f"{field} count exceeds resource limit",
                        "budget",
                    )
                )
    if artifact == "scene":
        nodes = value.get("nodes")
        for index, node in enumerate(nodes if isinstance(nodes, list) else []):
            source = node.get("source") if isinstance(node, dict) else None
            component_path = source.get("component_path") if isinstance(source, dict) else None
            if isinstance(component_path, list) and len(component_path) > limits.hierarchy_depth:
                issues.append(
                    _issue(
                        "resource_limit_exceeded",
                        f"/nodes/{index}/source/component_path",
                        "hierarchy depth exceeds resource limit",
                        "budget",
                    )
                )
        connectors = value.get("connectors")
        connector_records = connectors if isinstance(connectors, list) else []
        forward_edges = {
            connector.get("connector_snapshot_id"): connector.get(
                "forwarded_from", {}
            ).get("source_connector_snapshot_id")
            for connector in connector_records
            if isinstance(connector, dict)
            and connector.get("anchor_kind") == "forwarded"
            and isinstance(connector.get("forwarded_from"), dict)
        }
        for start in forward_edges:
            current = start
            seen: set[Any] = set()
            depth = 0
            while current in forward_edges and current not in seen:
                seen.add(current)
                current = forward_edges[current]
                depth += 1
                if depth > limits.forwarded_connector_depth:
                    issues.append(
                        _issue(
                            "resource_limit_exceeded",
                            "/connectors",
                            "forwarded connector depth exceeds resource limit",
                            "budget",
                        )
                    )
                    break
    return issues


def resource_count_issues(
    value: Any,
    artifact: str,
    *,
    limits: SceneResourceLimits = BASE_LIMITS,
) -> tuple[SceneValidationIssue, ...]:
    """Return early collection and graph-depth resource issues."""

    if artifact not in SCHEMA_FILES:
        raise ValueError(f"unknown scene artifact: {artifact}")
    return _report(_resource_count_issues(value, artifact, limits=limits)).issues


def _sorted_unique(values: Sequence[str]) -> bool:
    return list(values) == sorted(set(values), key=_utf8_key)


def _array_order_issues(value: Any) -> list[SceneValidationIssue]:
    issues: list[SceneValidationIssue] = []
    if not isinstance(value, dict):
        return issues
    for key, child in value.items():
        if key in _SET_ARRAY_KEYS and isinstance(child, list) and all(isinstance(item, str) for item in child):
            if not _sorted_unique(child):
                issues.append(_issue("array_order_invalid", f"/{key}", "set-like array is not sorted and unique"))
    for path, child in _walk_json(value):
        if not path or not isinstance(child, list):
            continue
        key = path[-1]
        if key in _SET_ARRAY_KEYS and all(isinstance(item, str) for item in child) and not _sorted_unique(child):
            issues.append(_issue("array_order_invalid", _pointer(path), "set-like array is not sorted and unique"))
    for collection, id_key in _COLLECTION_SORT_KEYS.items():
        records = value.get(collection)
        if isinstance(records, list) and all(isinstance(record, dict) and isinstance(record.get(id_key), str) for record in records):
            ids = [record[id_key] for record in records]
            if ids != sorted(ids, key=_utf8_key) or len(ids) != len(set(ids)):
                issues.append(_issue("array_order_invalid", f"/{collection}", f"{collection} is not sorted and unique by {id_key}"))
    return issues


def _is_vec3(value: Any) -> bool:
    return isinstance(value, list) and len(value) == 3 and all(isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(item) for item in value)


def _transform_issue(transform: Any, path: str) -> SceneValidationIssue | None:
    if not isinstance(transform, dict) or not all(_is_vec3(transform.get(key)) for key in ("origin", "x_axis", "y_axis", "z_axis")):
        return None  # Structural schema owns this error.
    origin = transform["origin"]
    x_axis = transform["x_axis"]
    y_axis = transform["y_axis"]
    z_axis = transform["z_axis"]
    if any(abs(component) > 1e12 for component in origin):
        return _issue("transform_invalid", path, "transform origin exceeds the scene coordinate limit")
    dot = lambda left, right: sum(a * b for a, b in zip(left, right))
    norm = lambda vector: math.sqrt(dot(vector, vector))
    if any(abs(norm(axis) - 1.0) > 1e-12 for axis in (x_axis, y_axis, z_axis)):
        return _issue("transform_invalid", path, "transform axes must be unit vectors within 1e-12")
    if any(abs(dot(left, right)) > 1e-12 for left, right in ((x_axis, y_axis), (x_axis, z_axis), (y_axis, z_axis))):
        return _issue("transform_invalid", path, "transform axes must be pairwise orthogonal within 1e-12")
    cross = [
        x_axis[1] * y_axis[2] - x_axis[2] * y_axis[1],
        x_axis[2] * y_axis[0] - x_axis[0] * y_axis[2],
        x_axis[0] * y_axis[1] - x_axis[1] * y_axis[0],
    ]
    if any(abs(actual - expected) > 1e-12 for actual, expected in zip(cross, z_axis)):
        return _issue("transform_invalid", path, "z_axis must equal cross(x_axis, y_axis) within 1e-12")
    return None


def _analytic_geometry_issues(geometry: Any, path: str) -> list[SceneValidationIssue]:
    if not isinstance(geometry, dict):
        return []
    geometry_type = geometry.get("type")
    direction_fields = {
        "line": ("direction",),
        "circle": ("normal", "x_direction"),
        "ellipse": ("normal", "x_direction"),
        "plane": ("normal", "x_direction"),
        "cylinder": ("axis", "x_direction"),
        "cone": ("axis", "x_direction"),
        "sphere": ("axis", "x_direction"),
        "torus": ("axis", "x_direction"),
    }.get(geometry_type, ())
    coordinate_fields = {
        "point": ("position",),
        "line": ("origin",),
        "circle": ("center",),
        "ellipse": ("center",),
        "plane": ("origin",),
        "cylinder": ("origin",),
        "cone": ("origin",),
        "sphere": ("center",),
        "torus": ("center",),
    }.get(geometry_type, ())
    issues: list[SceneValidationIssue] = []
    for field in coordinate_fields:
        vector = geometry.get(field)
        if _is_vec3(vector) and any(abs(component) > 1e12 for component in vector):
            issues.append(_issue("analytic_geometry_invalid", path + "/" + field, "analytic coordinate exceeds the scene coordinate limit"))
    if not direction_fields or not all(_is_vec3(geometry.get(field)) for field in direction_fields):
        return issues
    vectors = [geometry[field] for field in direction_fields]
    for field, vector in zip(direction_fields, vectors):
        norm = math.sqrt(sum(component * component for component in vector))
        if abs(norm - 1.0) > 1e-12:
            issues.append(_issue("analytic_geometry_invalid", path + "/" + field, "analytic direction must be a unit vector within 1e-12"))
    if len(vectors) == 2:
        dot = sum(left * right for left, right in zip(*vectors))
        if abs(dot) > 1e-12:
            issues.append(_issue("analytic_geometry_invalid", path, "analytic axis and x_direction must be orthogonal within 1e-12"))
    return issues


def _bounds_issues(bounds: Any, path: str, point: Sequence[float] | None = None) -> list[SceneValidationIssue]:
    if not isinstance(bounds, dict) or not _is_vec3(bounds.get("min")) or not _is_vec3(bounds.get("max")):
        return []
    minimum, maximum = bounds["min"], bounds["max"]
    issues: list[SceneValidationIssue] = []
    if any(low > high for low, high in zip(minimum, maximum)):
        issues.append(_issue("bounds_invalid", path, "bounds min exceeds max"))
    if any(abs(component) > 1e12 for component in (*minimum, *maximum)):
        issues.append(_issue("bounds_invalid", path, "bounds exceed the scene coordinate limit"))
    if point is not None and _is_vec3(list(point)):
        max_abs = max(1.0, *(abs(component) for component in (*minimum, *maximum, *point)))
        epsilon = max(1e-9, 1e-12 * max_abs)
        if any(value < low - epsilon or value > high + epsilon for value, low, high in zip(point, minimum, maximum)):
            issues.append(_issue("bounds_invalid", path, "point or centroid is outside bounds"))
    return issues


def _encode_segment(value: str) -> str:
    return quote(value, safe="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~")


def _root_id_from_definition(definition: Mapping[str, Any]) -> Any:
    source = definition.get("source")
    return source.get("root_id") if isinstance(source, dict) else None


def _scene_semantic_issues(scene: Mapping[str, Any]) -> list[SceneValidationIssue]:
    issues: list[SceneValidationIssue] = []
    if scene.get("revision") != compute_scene_revision(scene):
        issues.append(_issue("revision_mismatch", "/revision", "scene revision does not match canonical draft hash"))
    source = scene.get("source")
    source_kind = source.get("kind") if isinstance(source, dict) else None
    graph_id = source.get("graph_id") if isinstance(source, dict) else None
    source_id = source.get("source_id") if isinstance(source, dict) else None
    options = scene.get("compile_options", {})
    presentation_source = scene.get("presentation_source")
    if isinstance(options, dict) and isinstance(source, dict):
        embed_source = options.get("embed_source")
        embedded = "embedded_artifact_uri" in source
        if source_kind == "manual" and (embed_source or embedded):
            issues.append(_issue("source_matrix_invalid", "/source", "manual source cannot be embedded"))
        elif source_kind in {"model", "imported"} and embed_source != embedded:
            issues.append(_issue("source_matrix_invalid", "/source", "embed_source does not match source embedding fields"))
        source_files = source.get("source_files", [])
        if isinstance(source_files, list):
            paths = [record.get("path") for record in source_files if isinstance(record, dict)]
            if paths != sorted(paths, key=lambda value: str(value).encode("utf-8")) or len(paths) != len(set(paths)):
                issues.append(_issue("array_order_invalid", "/source/source_files", "source_files is not sorted and unique by path"))
            casefold_paths: dict[str, int] = {}
            for index, record in enumerate(source_files):
                if not isinstance(record, dict):
                    continue
                path = record.get("path")
                if isinstance(path, str):
                    segments = path.split("/")
                    if (
                        not _SOURCE_PATH_RE.fullmatch(path)
                        or any(segment in {"", ".", ".."} for segment in segments)
                    ):
                        issues.append(_issue("source_matrix_invalid", f"/source/source_files/{index}/path", "source file path is not archive-safe"))
                    folded = path.lower()
                    if folded in casefold_paths and paths[casefold_paths[folded]] != path:
                        issues.append(_issue("source_matrix_invalid", f"/source/source_files/{index}/path", "source file paths collide case-insensitively"))
                    else:
                        casefold_paths[folded] = index
                    if record.get("uri") != f"sources/{path}":
                        issues.append(_issue("source_matrix_invalid", f"/source/source_files/{index}/uri", "source file URI does not preserve the project-relative path"))
        embed_presentation = options.get("embed_presentation")
        if presentation_source is None and embed_presentation:
            issues.append(_issue("source_matrix_invalid", "/compile_options/embed_presentation", "presentation embedding requires presentation_source"))
        if isinstance(presentation_source, dict) and embed_presentation != ("embedded_artifact_uri" in presentation_source):
            issues.append(_issue("source_matrix_invalid", "/presentation_source", "embed_presentation does not match presentation embedding fields"))

    definitions = scene.get("definitions", [])
    definition_map = {record.get("definition_id"): record for record in definitions if isinstance(record, dict)}
    nodes = scene.get("nodes", [])
    node_map = {record.get("node_id"): record for record in nodes if isinstance(record, dict)}
    appearances = scene.get("appearances", [])
    appearance_map = {record.get("appearance_id"): record for record in appearances if isinstance(record, dict)}
    geometry_map = {record.get("asset_id"): record for record in scene.get("geometry_assets", []) if isinstance(record, dict)}
    edge_map = {record.get("asset_id"): record for record in scene.get("edge_assets", []) if isinstance(record, dict)}
    entity_map = {record.get("entity_asset_id"): record for record in scene.get("entity_assets", []) if isinstance(record, dict)}

    for index, definition in enumerate(definitions):
        if not isinstance(definition, dict):
            continue
        path = f"/definitions/{index}"
        kind = definition.get("kind")
        nested = definition.get("source", {})
        nested_kind = nested.get("kind") if isinstance(nested, dict) else None
        root_id = nested.get("root_id") if isinstance(nested, dict) else None
        valid_source = {
            "model": {"part": "product_model", "assembly": "product_model", "shape": "model_output"},
            "manual": {"part": "product_manual", "assembly": "product_manual", "shape": "manual"},
            "imported": {"shape": "imported"},
        }.get(source_kind, {}).get(kind)
        if nested_kind != valid_source:
            issues.append(_issue("source_matrix_invalid", path + "/source", "definition source is incompatible with scene and definition kinds"))
        if nested_kind in {"product_model", "model_output"} and nested.get("graph_id") != graph_id:
            issues.append(_issue("source_matrix_invalid", path + "/source/graph_id", "definition graph_id differs from scene graph_id"))
        if nested_kind == "manual" and nested.get("source_id") != source_id:
            issues.append(_issue("source_matrix_invalid", path + "/source/source_id", "definition manual source_id differs from scene source_id"))
        if nested_kind in {"product_model", "product_manual"}:
            expected_semantic = "Part" if kind == "part" else "Assembly"
            if nested.get("semantic_type") != expected_semantic:
                issues.append(_issue("source_matrix_invalid", path + "/source/semantic_type", "semantic_type differs from definition kind"))
            expected_id = f"definition/{root_id}/{kind}/{_encode_segment(str(nested.get('semantic_id', '')))}"
        elif nested_kind == "model_output":
            expected_id = f"definition/{root_id}/shape/model/{_encode_segment(str(nested.get('graph_id', '')))}/{_encode_segment(str(nested.get('node_id', '')))}/{nested.get('output_slot')}"
        elif nested_kind == "imported":
            expected_id = f"definition/{root_id}/shape/imported/{_encode_segment(str(nested.get('source_element_id', '')))}"
        else:
            expected_id = f"definition/{root_id}/shape/manual/{_encode_segment(str(nested.get('source_id', '')))}"
        if definition.get("definition_id") != expected_id:
            issues.append(_issue("source_matrix_invalid", path + "/definition_id", "definition_id does not match its source-derived structural ID"))
        for field, registry in (("geometry_asset_id", geometry_map), ("edge_asset_id", edge_map), ("entity_asset_id", entity_map), ("appearance_id", appearance_map)):
            reference = definition.get(field)
            if reference is not None and reference not in registry:
                issues.append(_issue("reference_missing", path + "/" + field, f"referenced {field} does not exist"))

    roots: list[Mapping[str, Any]] = []
    sibling_orders: dict[Any, list[int]] = {}
    referenced_definitions: set[Any] = set()
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            continue
        path = f"/nodes/{index}"
        definition = definition_map.get(node.get("definition_id"))
        if definition is None:
            issues.append(_issue("reference_missing", path + "/definition_id", "node definition does not exist"))
            continue
        referenced_definitions.add(node.get("definition_id"))
        node_source = node.get("source", {})
        node_kind = node_source.get("kind") if isinstance(node_source, dict) else None
        root_id = node_source.get("root_id") if isinstance(node_source, dict) else None
        definition_root = _root_id_from_definition(definition)
        expected_node_kind = "product_occurrence" if definition.get("kind") in {"part", "assembly"} else "shape_root"
        if node_kind != expected_node_kind or root_id != definition_root:
            issues.append(_issue("source_matrix_invalid", path + "/source", "node source kind/root does not match definition"))
        if node_kind == "product_occurrence":
            component_path = node_source.get("component_path", [])
            expected_node_id = "instance/" + str(root_id) + "".join("/" + _encode_segment(str(segment)) for segment in component_path)
            expected_parent = None if not component_path else "instance/" + str(root_id) + "".join("/" + _encode_segment(str(segment)) for segment in component_path[:-1])
        else:
            expected_node_id = f"instance/{root_id}"
            expected_parent = None
        if node.get("node_id") != expected_node_id:
            issues.append(_issue("hierarchy_invalid", path + "/node_id", "node_id does not match source-derived structural ID"))
        if node.get("parent_node_id") != expected_parent:
            issues.append(_issue("hierarchy_invalid", path + "/parent_node_id", "parent_node_id does not match component path"))
        if node.get("parent_node_id") is None:
            roots.append(node)
        elif node.get("parent_node_id") not in node_map:
            issues.append(_issue("reference_missing", path + "/parent_node_id", "parent node does not exist"))
        sibling_orders.setdefault(node.get("parent_node_id"), []).append(node.get("order"))
        override = node.get("appearance_override_id")
        if node.get("selectable") is not True:
            issues.append(_issue("source_matrix_invalid", path + "/selectable", "node selectability must use the deterministic true default"))
        if presentation_source is None:
            if node.get("visible") is not True:
                issues.append(_issue("source_matrix_invalid", path + "/visible", "node visibility requires presentation_source"))
            if override is not None:
                issues.append(_issue("source_matrix_invalid", path + "/appearance_override_id", "appearance override requires presentation_source"))
        if override is not None and override not in appearance_map:
            issues.append(_issue("reference_missing", path + "/appearance_override_id", "appearance override does not exist"))
        if definition.get("kind") == "assembly" and override is not None:
            issues.append(_issue("source_matrix_invalid", path + "/appearance_override_id", "assembly occurrence cannot carry appearance override"))
        transform_issue = _transform_issue(node.get("transform"), path + "/transform")
        if transform_issue:
            issues.append(transform_issue)
    for parent, orders in sibling_orders.items():
        if all(isinstance(order, int) and not isinstance(order, bool) for order in orders) and sorted(orders) != list(range(len(orders))):
            issues.append(_issue("hierarchy_invalid", "/nodes", f"sibling order under {parent!r} is not continuous"))
    root_ids = [node.get("source", {}).get("root_id") for node in roots if isinstance(node.get("source"), dict)]
    expected_roots = sorted(root_ids, key=lambda value: str(value).encode("utf-8"))
    actual_roots = [root.get("source", {}).get("root_id") for root in sorted(roots, key=lambda item: item.get("order", -1))]
    if actual_roots != expected_roots:
        issues.append(_issue("hierarchy_invalid", "/nodes", "root order does not match unsigned UTF-8 root_id order"))
    definition_ids = set(definition_map)
    if definition_ids or node_map:
        if referenced_definitions != definition_ids:
            issues.append(_issue("hierarchy_invalid", "/nodes", "every definition must be instantiated by at least one node"))
        definition_root_ids = {_root_id_from_definition(definition) for definition in definition_map.values()}
        root_counts = {
            root_id: sum(
                1
                for root in roots
                if isinstance(root.get("source"), dict)
                and root["source"].get("root_id") == root_id
            )
            for root_id in definition_root_ids
        }
        if any(count != 1 for count in root_counts.values()):
            issues.append(_issue("hierarchy_invalid", "/nodes", "each definition root_id must have exactly one root occurrence"))

    used_assets = {definition.get(field) for definition in definitions if isinstance(definition, dict) for field in ("geometry_asset_id", "edge_asset_id", "entity_asset_id") if definition.get(field) is not None}
    declared_assets = set(geometry_map) | set(edge_map) | set(entity_map)
    if used_assets != declared_assets:
        issues.append(_issue("reference_missing", "/definitions", "asset records must be referenced exactly by definitions"))
    for collection, kind in (("geometry_assets", "geometry"), ("edge_assets", "edges")):
        for index, asset in enumerate(scene.get(collection, [])):
            if not isinstance(asset, dict):
                continue
            path = f"/{collection}/{index}"
            if asset.get("asset_id") != asset.get("content_hash"):
                issues.append(_issue("source_matrix_invalid", path + "/asset_id", "asset_id must equal content_hash"))
            digest = str(asset.get("asset_id", "")).removeprefix("sha256:")
            if asset.get("uri") != f"{kind}/sha256-{digest}.glb":
                issues.append(_issue("source_matrix_invalid", path + "/uri", "asset URI does not match content hash"))
            tessellation = asset.get("tessellation", {})
            if isinstance(tessellation, dict) and isinstance(options, dict):
                if tessellation.get("linear_tolerance") != options.get("linear_tolerance"):
                    issues.append(_issue("source_matrix_invalid", path + "/tessellation/linear_tolerance", "asset tolerance differs from compile options"))
                if collection == "geometry_assets" and tessellation.get("angular_tolerance") != options.get("angular_tolerance"):
                    issues.append(_issue("source_matrix_invalid", path + "/tessellation/angular_tolerance", "asset tolerance differs from compile options"))
            issues.extend(_bounds_issues(asset.get("scene_local_bounds"), path + "/scene_local_bounds"))
    for index, asset in enumerate(scene.get("entity_assets", [])):
        if not isinstance(asset, dict):
            continue
        path = f"/entity_assets/{index}"
        if asset.get("entity_asset_id") != asset.get("content_hash"):
            issues.append(_issue("source_matrix_invalid", path + "/entity_asset_id", "entity_asset_id must equal content_hash"))
        digest = str(asset.get("entity_asset_id", "")).removeprefix("sha256:")
        if asset.get("uri") != f"entities/sha256-{digest}.json":
            issues.append(_issue("source_matrix_invalid", path + "/uri", "entity URI does not match content hash"))
    for index, appearance in enumerate(appearances):
        if not isinstance(appearance, dict):
            continue
        path = f"/appearances/{index}"
        draft = dict(appearance)
        draft.pop("appearance_id", None)
        expected = "appearance/evaluated/" + hashlib.sha256(canonical_json_bytes(draft)).hexdigest()
        if appearance.get("appearance_id") != expected:
            issues.append(_issue("source_matrix_invalid", path + "/appearance_id", "appearance_id does not match content-derived identity"))
        appearance_source = appearance.get("source")
        if isinstance(appearance_source, dict):
            if appearance_source.get("kind") == "product_material" and source_kind not in {"model", "manual"}:
                issues.append(_issue("source_matrix_invalid", path + "/source", "product material source is incompatible with scene source"))
            if appearance_source.get("kind") == "product_material":
                matching_definitions = (
                    definition
                    for definition in definitions
                    if isinstance(definition, dict)
                    and definition.get("kind") == "part"
                    and definition.get("appearance_id") == appearance.get("appearance_id")
                )
                if not any(
                    _root_id_from_definition(definition) == appearance_source.get("root_id")
                    for definition in matching_definitions
                ):
                    issues.append(_issue("source_matrix_invalid", path + "/source/root_id", "product material appearance provenance does not match a Part definition root"))
            if appearance_source.get("kind") == "presentation":
                if not isinstance(presentation_source, dict) or appearance_source.get("presentation_id") != presentation_source.get("presentation_id"):
                    issues.append(_issue("source_matrix_invalid", path + "/source", "presentation appearance source does not match presentation_source"))

    connectors = scene.get("connectors", [])
    if source_kind == "imported" and connectors:
        issues.append(_issue("source_matrix_invalid", "/connectors", "imported scene connectors must be empty"))
    connector_map = {record.get("connector_snapshot_id"): record for record in connectors if isinstance(record, dict)}
    connector_ids_by_owner: dict[Any, set[Any]] = {}
    forward_edges: dict[Any, Any] = {}
    for index, connector in enumerate(connectors):
        if not isinstance(connector, dict):
            continue
        path = f"/connectors/{index}"
        owner = definition_map.get(connector.get("owner_definition_id"))
        if owner is None:
            issues.append(_issue("reference_missing", path + "/owner_definition_id", "connector owner definition does not exist"))
            continue
        owner_ids = connector_ids_by_owner.setdefault(connector.get("owner_definition_id"), set())
        if connector.get("connector_id") in owner_ids:
            issues.append(_issue("id_duplicate", path + "/connector_id", "connector_id is duplicated within owner definition"))
        owner_ids.add(connector.get("connector_id"))
        owner_source = owner.get("source", {})
        root_id = owner_source.get("root_id") if isinstance(owner_source, dict) else None
        owner_semantic = owner_source.get("semantic_id") if isinstance(owner_source, dict) else None
        expected_snapshot = f"connector/{root_id}/{owner.get('kind')}/{_encode_segment(str(owner_semantic))}/{_encode_segment(str(connector.get('connector_id', '')))}"
        if connector.get("connector_snapshot_id") != expected_snapshot:
            issues.append(_issue("connector_invalid", path + "/connector_snapshot_id", "connector snapshot ID does not match owner and connector IDs"))
        anchor_kind = connector.get("anchor_kind")
        if anchor_kind == "geometry" and owner.get("kind") != "part":
            issues.append(_issue("connector_invalid", path + "/owner_definition_id", "geometry connector owner must be a Part"))
        if anchor_kind == "placement" and owner.get("kind") not in {"part", "assembly"}:
            issues.append(_issue("connector_invalid", path + "/owner_definition_id", "connector owner must be a Product definition"))
        if anchor_kind == "forwarded" and owner.get("kind") != "assembly":
            issues.append(_issue("connector_invalid", path + "/owner_definition_id", "forwarded connector owner must be an Assembly"))
        connector_source = connector.get("source")
        if source_kind == "model":
            if not isinstance(connector_source, dict) or connector_source.get("kind") != "model_operation" or connector_source.get("graph_id") != graph_id:
                issues.append(_issue("connector_invalid", path + "/source", "model connector must use the scene graph model_operation source"))
            elif connector_source.get("output_slot") != 0:
                issues.append(_issue("connector_invalid", path + "/source/output_slot", "connector producer output_slot must be 0"))
        elif source_kind == "manual":
            if not isinstance(connector_source, dict) or connector_source != {"kind": "manual", "source_id": source_id}:
                issues.append(_issue("connector_invalid", path + "/source", "manual connector source must equal the top-level source_id"))
        transform_issue = _transform_issue(connector.get("local_transform"), path + "/local_transform")
        if transform_issue:
            issues.append(transform_issue)
        if anchor_kind == "forwarded":
            forwarded = connector.get("forwarded_from", {})
            source_snapshot = forwarded.get("source_connector_snapshot_id") if isinstance(forwarded, dict) else None
            source_connector = connector_map.get(source_snapshot)
            if source_connector is None or source_connector.get("owner_definition_id") != forwarded.get("source_definition_id") or source_connector.get("connector_id") != forwarded.get("source_connector_id"):
                issues.append(_issue("connector_invalid", path + "/forwarded_from", "forwarded connector source snapshot ownership is invalid"))
            forward_edges[connector.get("connector_snapshot_id")] = source_snapshot
            if isinstance(forwarded, dict) and forwarded.get("offset") is not None:
                transform_issue = _transform_issue(forwarded.get("offset"), path + "/forwarded_from/offset")
                if transform_issue:
                    issues.append(transform_issue)
            if isinstance(forwarded, dict) and owner.get("kind") == "assembly":
                owner_nodes = [
                    node
                    for node in nodes
                    if isinstance(node, dict)
                    and node.get("definition_id") == connector.get("owner_definition_id")
                    and isinstance(node.get("source"), dict)
                    and node["source"].get("kind") == "product_occurrence"
                ]
                source_children: list[Mapping[str, Any]] = []
                for owner_node in owner_nodes:
                    owner_node_source = owner_node["source"]
                    expected_path = [
                        *owner_node_source.get("component_path", []),
                        forwarded.get("source_component_id"),
                    ]
                    matches = [
                        node
                        for node in nodes
                        if isinstance(node, dict)
                        and isinstance(node.get("source"), dict)
                        and node["source"].get("kind") == "product_occurrence"
                        and node["source"].get("root_id")
                        == owner_node_source.get("root_id")
                        and node["source"].get("component_path") == expected_path
                        and node.get("parent_node_id") == owner_node.get("node_id")
                    ]
                    if (
                        len(matches) != 1
                        or matches[0].get("definition_id")
                        != forwarded.get("source_definition_id")
                    ):
                        issues.append(
                            _issue(
                                "connector_invalid",
                                path + "/forwarded_from",
                                "forwarded connector source component is not one exact direct child",
                            )
                        )
                    else:
                        source_children.append(matches[0])
                if source_children and any(
                    child.get("transform") != source_children[0].get("transform")
                    for child in source_children[1:]
                ):
                    issues.append(
                        _issue(
                            "connector_invalid",
                            path + "/forwarded_from",
                            "forwarded connector source child transforms differ between owner occurrences",
                        )
                    )
                if source_children and isinstance(source_connector, dict):
                    child_transform = source_children[0].get("transform")
                    source_transform = source_connector.get("local_transform")
                    offset = forwarded.get("offset") or {
                        "origin": [0, 0, 0],
                        "x_axis": [1, 0, 0],
                        "y_axis": [0, 1, 0],
                        "z_axis": [0, 0, 1],
                    }
                    if (
                        all(
                            isinstance(value, dict)
                            and _transform_issue(value, "") is None
                            for value in (child_transform, source_transform, offset)
                        )
                        and isinstance(connector.get("local_transform"), dict)
                        and _transform_issue(connector["local_transform"], "") is None
                    ):
                        expected_transform = compose_rigid_transforms(
                            compose_rigid_transforms(child_transform, source_transform),
                            offset,
                        )
                        if not rigid_transforms_equal(
                            connector["local_transform"], expected_transform
                        ):
                            issues.append(
                                _issue(
                                    "connector_invalid",
                                    path + "/local_transform",
                                    "forwarded connector transform does not match child, source, and offset composition",
                                )
                            )
    for start in forward_edges:
        seen: set[Any] = set()
        current = start
        while current in forward_edges:
            if current in seen:
                issues.append(_issue("connector_invalid", "/connectors", "forwarded connector graph contains a cycle"))
                break
            seen.add(current)
            current = forward_edges[current]
    for index, camera in enumerate(scene.get("cameras", [])):
        if not isinstance(camera, dict):
            continue
        path = f"/cameras/{index}"
        if presentation_source is None:
            issues.append(_issue("source_matrix_invalid", path, "evaluated scene camera requires presentation_source"))
        if camera.get("parent_node_id") is not None and camera.get("parent_node_id") not in node_map:
            issues.append(_issue("reference_missing", path + "/parent_node_id", "camera parent node does not exist"))
        if isinstance(camera.get("near"), (int, float)) and isinstance(camera.get("far"), (int, float)) and camera["far"] <= camera["near"]:
            issues.append(_issue("bounds_invalid", path + "/far", "camera far must exceed near"))
        transform_issue = _transform_issue(camera.get("transform"), path + "/transform")
        if transform_issue:
            issues.append(transform_issue)
    return issues


def validate_scene_manifest(
    scene: Any, *, limits: SceneResourceLimits = BASE_LIMITS
) -> SceneValidationReport:
    issues = _serialized_size_issues(scene, "scene", limits=limits)
    value, parse_issues = _parse_input(
        scene,
        require_canonical=isinstance(scene, (bytes, bytearray, memoryview, str)),
    )
    issues.extend(parse_issues)
    if value is None and issues:
        return _report(issues, artifact="scene")
    issues.extend(_domain_issues(value, limits=limits))
    issues.extend(_resource_count_issues(value, "scene", limits=limits))
    if _has_unsafe_depth(issues):
        return _report(issues, artifact="scene")
    issues.extend(_schema_issues(value, "scene"))
    if isinstance(value, dict) and not _has_blocking_issues(issues):
        issues.extend(_array_order_issues(value))
        issues.extend(_scene_semantic_issues(value))
    return _report(issues, artifact="scene")


def _entity_semantic_issues(asset: Mapping[str, Any]) -> list[SceneValidationIssue]:
    issues: list[SceneValidationIssue] = []
    entities = asset.get("entities", [])
    entity_map = {entity.get("entity_id"): entity for entity in entities if isinstance(entity, dict)}
    if len(entity_map) != len(entities):
        issues.append(_issue("id_duplicate", "/entities", "entity IDs must be unique"))
    for kind in ("solid", "face", "edge", "vertex"):
        actual = {
            entity_id
            for entity_id, entity in entity_map.items()
            if entity.get("kind") == kind and isinstance(entity_id, str)
        }
        expected = {f"entity/{kind}/{index}" for index in range(len(actual))}
        if actual != expected:
            issues.append(_issue("entity_topology_invalid", "/entities", f"{kind} entity IDs must use dense zero-based ordinals"))
    kind_geometry = {
        "solid": {"brep_solid"},
        "face": {"plane", "cylinder", "cone", "sphere", "torus", "bspline_surface", "other_surface"},
        "edge": {"line", "circle", "ellipse", "bspline_curve", "other_curve"},
        "vertex": {"point"},
    }
    expected_property_keys = {
        "solid": {"quality", "bounds", "volume", "surface_area", "centroid"},
        "face": {"quality", "bounds", "area", "centroid", "orientation"},
        "edge": {"quality", "bounds", "length", "centroid"},
        "vertex": {"quality", "bounds", "position"},
    }
    for index, entity in enumerate(entities):
        if not isinstance(entity, dict):
            continue
        path = f"/entities/{index}"
        entity_id = entity.get("entity_id")
        kind = entity.get("kind")
        if isinstance(entity_id, str) and not entity_id.startswith(f"entity/{kind}/"):
            issues.append(_issue("entity_topology_invalid", path + "/entity_id", "entity ID kind differs from entity kind"))
        geometry = entity.get("geometry", {})
        if isinstance(geometry, dict) and geometry.get("type") not in kind_geometry.get(kind, set()):
            issues.append(_issue("entity_topology_invalid", path + "/geometry/type", "geometry variant is incompatible with entity kind"))
        issues.extend(_analytic_geometry_issues(geometry, path + "/geometry"))
        properties = entity.get("properties", {})
        if isinstance(properties, dict) and set(properties) != expected_property_keys.get(kind):
            issues.append(_issue("entity_topology_invalid", path + "/properties", "property record is incompatible with entity kind"))
        parents = entity.get("parent_entity_ids", [])
        children = entity.get("child_entity_ids", [])
        if kind == "solid" and (parents or not children or any(entity_map.get(child, {}).get("kind") != "face" for child in children)):
            issues.append(_issue("entity_topology_invalid", path, "solid must own one or more faces and have no parent"))
        if kind == "face" and (len(parents) != 1 or entity_map.get(parents[0], {}).get("kind") != "solid" or not children or any(entity_map.get(child, {}).get("kind") != "edge" for child in children)):
            issues.append(_issue("entity_topology_invalid", path, "face must have one solid parent and one or more edge children"))
        if kind == "edge" and (not parents or any(entity_map.get(parent, {}).get("kind") != "face" for parent in parents) or len(children) not in {1, 2} or any(entity_map.get(child, {}).get("kind") != "vertex" for child in children)):
            issues.append(_issue("entity_topology_invalid", path, "edge must have face parents and one or two vertex children"))
        if kind == "vertex" and (not parents or any(entity_map.get(parent, {}).get("kind") != "edge" for parent in parents) or children):
            issues.append(_issue("entity_topology_invalid", path, "vertex must have edge parents and no children"))
        for parent in parents:
            if parent not in entity_map:
                issues.append(_issue("reference_missing", path + "/parent_entity_ids", "parent entity does not exist"))
            elif entity_id not in entity_map[parent].get("child_entity_ids", []):
                issues.append(_issue("entity_topology_invalid", path + "/parent_entity_ids", "parent relation is not reciprocal"))
        for child in children:
            if child not in entity_map:
                issues.append(_issue("reference_missing", path + "/child_entity_ids", "child entity does not exist"))
            elif entity_id not in entity_map[child].get("parent_entity_ids", []):
                issues.append(_issue("entity_topology_invalid", path + "/child_entity_ids", "child relation is not reciprocal"))
        source = entity.get("source", {})
        if isinstance(source, dict) and source.get("kind") == "model_topology":
            expected = {"solid": "SOLID", "face": "FACE", "edge": "EDGE", "vertex": "VERTEX"}.get(kind)
            if source.get("topology_kind") != expected:
                issues.append(_issue("source_matrix_invalid", path + "/source/topology_kind", "topology source kind differs from entity kind"))
        frame = entity.get("sdk_connector_frame")
        if kind == "solid" and frame is not None:
            issues.append(_issue("connector_invalid", path + "/sdk_connector_frame", "solid connector frame must be null"))
        if kind in {"face", "vertex"} and frame is None:
            issues.append(_issue("connector_invalid", path + "/sdk_connector_frame", "face and vertex connector frames must be present"))
        if frame is not None:
            transform_issue = _transform_issue(frame, path + "/sdk_connector_frame")
            if transform_issue:
                issues.append(transform_issue)
        status = entity.get("render_status")
        if kind != "edge" and status != "rendered":
            issues.append(_issue("entity_topology_invalid", path + "/render_status", "only edges may be degenerate"))
        if kind == "solid" and entity.get("connector_binding_status") != "not_applicable":
            issues.append(_issue("connector_invalid", path + "/connector_binding_status", "solid binding status must be not_applicable"))
        if kind == "edge" and frame is None and entity.get("connector_binding_status") not in {"frame_undefined", "owner_not_part", "source_not_model"}:
            issues.append(_issue("connector_invalid", path + "/connector_binding_status", "edge without frame cannot be supported"))
        if kind == "vertex" and isinstance(geometry, dict):
            point = geometry.get("position")
            if isinstance(properties, dict):
                if properties.get("position") != point:
                    issues.append(_issue("bounds_invalid", path + "/properties/position", "vertex property position differs from geometry point"))
                issues.extend(_bounds_issues(properties.get("bounds"), path + "/properties/bounds", point))
        elif isinstance(properties, dict):
            issues.extend(_bounds_issues(properties.get("bounds"), path + "/properties/bounds", properties.get("centroid")))

    face_ids = {entity_id for entity_id, entity in entity_map.items() if entity.get("kind") == "face"}
    rendered_edge_ids = {entity_id for entity_id, entity in entity_map.items() if entity.get("kind") == "edge" and entity.get("render_status") == "rendered"}
    degenerate_edge_ids = {entity_id for entity_id, entity in entity_map.items() if entity.get("kind") == "edge" and entity.get("render_status") == "degenerate"}
    for groups_key, expected_ids, divisor in (("face_groups", face_ids, 3), ("edge_groups", rendered_edge_ids, 2)):
        groups = asset.get(groups_key, [])
        group_ids = [group.get("entity_id") for group in groups if isinstance(group, dict)]
        if set(group_ids) != expected_ids or len(group_ids) != len(set(group_ids)):
            issues.append(_issue("entity_range_invalid", f"/{groups_key}", f"{groups_key} do not map exactly one group per rendered entity"))
        expected_first = 0
        for index, group in enumerate(groups):
            if not isinstance(group, dict):
                continue
            path = f"/{groups_key}/{index}"
            if group.get("group_id") != index or group.get("first_index") != expected_first:
                issues.append(_issue("entity_range_invalid", path, "group IDs and ranges must be continuous"))
            count = group.get("index_count")
            if isinstance(count, int) and not isinstance(count, bool):
                if count <= 0 or count % divisor:
                    issues.append(_issue("entity_range_invalid", path + "/index_count", "group count has invalid primitive cardinality"))
                expected_first += count
    if any(group.get("entity_id") in degenerate_edge_ids for group in asset.get("edge_groups", []) if isinstance(group, dict)):
        issues.append(_issue("entity_range_invalid", "/edge_groups", "degenerate edges must not have render groups"))
    return issues


def validate_entity_asset(
    asset: Any, *, limits: SceneResourceLimits = BASE_LIMITS
) -> SceneValidationReport:
    issues = _serialized_size_issues(asset, "entities", limits=limits)
    value, parse_issues = _parse_input(
        asset,
        require_canonical=isinstance(asset, (bytes, bytearray, memoryview, str)),
    )
    issues.extend(parse_issues)
    if value is None and issues:
        return _report(issues, artifact="entities")
    issues.extend(_domain_issues(value, limits=limits))
    issues.extend(_resource_count_issues(value, "entities", limits=limits))
    if _has_unsafe_depth(issues):
        return _report(issues, artifact="entities")
    issues.extend(_schema_issues(value, "entities"))
    if isinstance(value, dict) and not _has_blocking_issues(issues):
        issues.extend(_array_order_issues(value))
        issues.extend(_entity_semantic_issues(value))
    return _report(issues, artifact="entities")


def _presentation_semantic_issues(value: Mapping[str, Any]) -> list[SceneValidationIssue]:
    issues: list[SceneValidationIssue] = []
    appearances = value.get("appearances", [])
    names = [record.get("name") for record in appearances if isinstance(record, dict)]
    if len(names) != len(set(names)):
        issues.append(_issue("id_duplicate", "/appearances", "presentation appearance names must be unique"))
    name_set = set(names)
    overrides = value.get("node_overrides", [])
    node_ids = [record.get("node_id") for record in overrides if isinstance(record, dict)]
    if len(node_ids) != len(set(node_ids)):
        issues.append(_issue("id_duplicate", "/node_overrides", "node overrides must target unique node IDs"))
    for index, override in enumerate(overrides):
        if isinstance(override, dict) and override.get("appearance_name") is not None and override.get("appearance_name") not in name_set:
            issues.append(_issue("presentation_reference_invalid", f"/node_overrides/{index}/appearance_name", "appearance_name does not exist"))
    cameras = value.get("cameras", [])
    camera_names = [record.get("name") for record in cameras if isinstance(record, dict)]
    if len(camera_names) != len(set(camera_names)):
        issues.append(_issue("id_duplicate", "/cameras", "presentation camera names must be unique"))
    for index, camera in enumerate(cameras):
        if not isinstance(camera, dict):
            continue
        if isinstance(camera.get("near"), (int, float)) and isinstance(camera.get("far"), (int, float)) and camera["far"] <= camera["near"]:
            issues.append(_issue("bounds_invalid", f"/cameras/{index}/far", "camera far must exceed near"))
        transform_issue = _transform_issue(camera.get("transform"), f"/cameras/{index}/transform")
        if transform_issue:
            issues.append(transform_issue)
    return issues


def validate_presentation(
    value: Any, *, limits: SceneResourceLimits = BASE_LIMITS
) -> SceneValidationReport:
    issues = _serialized_size_issues(value, "presentation", limits=limits)
    parsed, parse_issues = _parse_input(
        value,
        require_canonical=isinstance(value, (bytes, bytearray, memoryview, str)),
    )
    issues.extend(parse_issues)
    if parsed is None and issues:
        return _report(issues, artifact="presentation")
    issues.extend(_domain_issues(parsed, limits=limits))
    issues.extend(_resource_count_issues(parsed, "presentation", limits=limits))
    if _has_unsafe_depth(issues):
        return _report(issues, artifact="presentation")
    issues.extend(_schema_issues(parsed, "presentation"))
    if isinstance(parsed, dict) and not _has_blocking_issues(issues):
        issues.extend(_presentation_semantic_issues(parsed))
    return _report(issues, artifact="presentation")


def validate_connector_binding(
    value: Any, *, limits: SceneResourceLimits = BASE_LIMITS
) -> SceneValidationReport:
    issues = _serialized_size_issues(value, "connector_binding", limits=limits)
    parsed, parse_issues = _parse_input(
        value,
        require_canonical=isinstance(value, (bytes, bytearray, memoryview, str)),
    )
    issues.extend(parse_issues)
    if parsed is None and issues:
        return _report(issues, artifact="connector_binding")
    issues.extend(_domain_issues(parsed, limits=limits))
    if _has_unsafe_depth(issues):
        return _report(issues, artifact="connector_binding")
    issues.extend(_schema_issues(parsed, "connector_binding"))
    if isinstance(parsed, dict) and not _has_blocking_issues(issues):
        source_model = parsed.get("source_model", {})
        expected = parsed.get("target", {}).get("expected_source", {}) if isinstance(parsed.get("target"), dict) else {}
        if isinstance(source_model, dict) and isinstance(expected, dict) and source_model.get("graph_id") != expected.get("graph_id"):
            issues.append(_issue("source_matrix_invalid", "/target/expected_source/graph_id", "target graph differs from source model graph"))
        entity_id = parsed.get("target", {}).get("entity_id") if isinstance(parsed.get("target"), dict) else None
        if isinstance(entity_id, str) and entity_id.startswith("entity/vertex/") and parsed.get("target", {}).get("flip") is not False:
            issues.append(_issue("connector_invalid", "/target/flip", "vertex connector target requires flip=false"))
    return _report(issues, artifact="connector_binding")


def _normalized_product_issues(value: Mapping[str, Any]) -> list[SceneValidationIssue]:
    issues: list[SceneValidationIssue] = []
    connectors = value.get("connectors", [])
    connector_ids = [connector.get("connector_id") for connector in connectors if isinstance(connector, dict)]
    if len(connector_ids) != len(set(connector_ids)):
        issues.append(_issue("id_duplicate", "/connectors", "connector IDs must be unique"))
    if value.get("kind") == "assembly":
        components = value.get("components", [])
        component_ids = [component.get("component_id") for component in components if isinstance(component, dict)]
        if len(component_ids) != len(set(component_ids)):
            issues.append(_issue("id_duplicate", "/components", "component IDs must be unique"))
        component_set = set(component_ids)
        grounded = value.get("grounded_component_ids", [])
        if any(component_id not in component_set for component_id in grounded):
            issues.append(_issue("reference_missing", "/grounded_component_ids", "grounded component does not exist"))
        constraints = value.get("constraints", [])
        constraint_ids = [constraint.get("constraint_id") for constraint in constraints if isinstance(constraint, dict)]
        if len(constraint_ids) != len(set(constraint_ids)):
            issues.append(_issue("id_duplicate", "/constraints", "constraint IDs must be unique"))
        for index, constraint in enumerate(constraints):
            if not isinstance(constraint, dict):
                continue
            for ref_key in ("connector_a", "connector_b"):
                ref = constraint.get(ref_key)
                if isinstance(ref, dict) and ref.get("component_id") not in component_set:
                    issues.append(_issue("reference_missing", f"/constraints/{index}/{ref_key}/component_id", "constraint component does not exist"))
            for limit_key in ("distance_limit", "angle_limit"):
                limit = constraint.get(limit_key)
                if isinstance(limit, dict) and limit.get("lower_value") > limit.get("upper_value"):
                    issues.append(_issue("bounds_invalid", f"/constraints/{index}/{limit_key}", "constraint lower limit exceeds upper limit"))
    return issues


def validate_normalized_product(
    value: Any, *, limits: SceneResourceLimits = BASE_LIMITS
) -> SceneValidationReport:
    issues = _serialized_size_issues(value, "normalized_product", limits=limits)
    parsed, parse_issues = _parse_input(
        value,
        require_canonical=isinstance(value, (bytes, bytearray, memoryview, str)),
    )
    issues.extend(parse_issues)
    if parsed is None and issues:
        return _report(issues, artifact="normalized_product")
    issues.extend(_domain_issues(parsed, limits=limits))
    if _has_unsafe_depth(issues):
        return _report(issues, artifact="normalized_product")
    issues.extend(_schema_issues(parsed, "normalized_product"))
    if isinstance(parsed, dict) and not _has_blocking_issues(issues):
        issues.extend(_normalized_product_issues(parsed))
    return _report(issues, artifact="normalized_product")


def _package_reference_records(
    scene: Mapping[str, Any],
) -> tuple[dict[str, Mapping[str, Any]], list[SceneValidationIssue]]:
    records: dict[str, Mapping[str, Any]] = {}
    issues: list[SceneValidationIssue] = []

    def add(uri: Any, byte_length: Any, content_hash: Any, media_role: str) -> None:
        if not isinstance(uri, str):
            return
        record = {
            "byte_length": byte_length,
            "content_hash": content_hash,
            "media_role": media_role,
        }
        previous = records.get(uri)
        if previous is not None and previous != record:
            issues.append(_issue("package_member_set_invalid", "", "manifest records for one URI disagree on hash, length, or media role", "package"))
            return
        records[uri] = record

    for collection, media_role in (
        ("geometry_assets", "geometry"),
        ("edge_assets", "edge"),
        ("entity_assets", "entity"),
    ):
        for record in scene.get(collection, []):
            if isinstance(record, dict):
                add(record.get("uri"), record.get("byte_length"), record.get("content_hash"), media_role)
    source = scene.get("source")
    if isinstance(source, dict) and isinstance(source.get("embedded_artifact_uri"), str):
        add(
            source["embedded_artifact_uri"],
            source.get("embedded_artifact_byte_length"),
            source.get("artifact_hash"),
            "model_source" if source.get("kind") == "model" else "imported_source",
        )
        for source_file in source.get("source_files", []):
            if isinstance(source_file, dict):
                add(
                    source_file.get("uri"),
                    source_file.get("byte_length"),
                    source_file.get("content_hash"),
                    "python_source",
                )
    presentation = scene.get("presentation_source")
    if isinstance(presentation, dict) and isinstance(presentation.get("embedded_artifact_uri"), str):
        add(
            presentation["embedded_artifact_uri"],
            presentation.get("embedded_artifact_byte_length"),
            presentation.get("artifact_hash"),
            "presentation",
        )
    return records, issues


def _source_segment(
    content: str,
    *,
    line: int,
    column: int,
    end_line: int,
    end_column: int,
) -> str | None:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n")
    lines = normalized.splitlines(keepends=True)
    if not lines and normalized == "":
        return None
    if line < 1 or end_line < line or end_line > len(lines):
        return None
    start_text = lines[line - 1].removesuffix("\n")
    end_text = lines[end_line - 1].removesuffix("\n")
    if (
        column < 0
        or end_column < 0
        or column > len(start_text)
        or end_column > len(end_text)
        or (line == end_line and end_column < column)
    ):
        return None
    if line == end_line:
        return start_text[column:end_column]
    return "".join(
        [lines[line - 1][column:], *lines[line:end_line - 1], end_text[:end_column]]
    )


def _expected_callsite_id(source: Mapping[str, Any]) -> str:
    material = "\x1f".join(
        [
            source.get("path") or "",
            str(source.get("line")),
            str(source.get("column")),
            str(source.get("end_line")),
            str(source.get("end_column")),
            str(source.get("call_text")),
        ]
    )
    return "callsite_" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]


def _operation_source_issues(
    source: Any,
    *,
    path: str,
    source_files: Mapping[str, str],
) -> list[SceneValidationIssue]:
    if not isinstance(source, dict):
        return [_issue("source_matrix_invalid", path, "operation source must be an object")]
    issues: list[SceneValidationIssue] = []
    if set(source) != _SOURCE_KEYS:
        issues.append(_issue("source_matrix_invalid", path, "operation source fields do not match source mapping schema 1.0"))
    path_kind = source.get("path_kind")
    source_path = source.get("path")
    integers = {
        key: source.get(key)
        for key in ("line", "column", "end_line", "end_column")
    }
    valid_integers = all(
        isinstance(value, int) and not isinstance(value, bool)
        for value in integers.values()
    )
    if (
        source.get("schema_version") != "1.0"
        or path_kind not in {"project_relative", "unresolved"}
        or not valid_integers
        or integers["line"] < 1
        or integers["column"] < 0
        or integers["end_line"] < integers["line"]
        or integers["end_column"] < 0
        or not isinstance(source.get("call_text"), str)
        or not isinstance(source.get("callsite_id"), str)
        or not re.fullmatch(r"callsite_[0-9a-f]{16}", source.get("callsite_id", ""))
        or not isinstance(source.get("assignment_targets"), list)
        or not all(isinstance(value, str) and value for value in source.get("assignment_targets", []))
    ):
        issues.append(_issue("source_matrix_invalid", path, "operation source values do not match source mapping schema 1.0"))
        return issues
    if path_kind == "unresolved":
        if source_path is not None:
            issues.append(_issue("source_matrix_invalid", path + "/path", "unresolved operation source path must be null"))
    elif not isinstance(source_path, str) or source_path not in source_files:
        issues.append(_issue("source_matrix_invalid", path + "/path", "operation source path does not resolve to an embedded source file"))
    else:
        segment = _source_segment(
            source_files[source_path],
            line=integers["line"],
            column=integers["column"],
            end_line=integers["end_line"],
            end_column=integers["end_column"],
        )
        if segment is None or segment != source.get("call_text"):
            issues.append(_issue("source_matrix_invalid", path, "operation source span does not match embedded source text"))
    if source.get("callsite_id") != _expected_callsite_id(source):
        issues.append(_issue("source_matrix_invalid", path + "/callsite_id", "operation callsite_id does not match its canonical source span"))
    return issues


def _embedded_model_issues(
    scene: Mapping[str, Any],
    payload: bytes,
    *,
    source_files: Mapping[str, str],
    entity_payloads: Mapping[str, Mapping[str, Any]],
) -> list[SceneValidationIssue]:
    prefix = "/model/model.json"
    try:
        model = parse_strict_json(payload)
    except DuplicateKeyError as exc:
        return [_issue("duplicate_json_key", "", str(exc), "parse")]
    except UnicodeDecodeError as exc:
        return [_issue("invalid_utf8", prefix, str(exc), "parse")]
    except ValueError as exc:
        return [_issue("schema_invalid", prefix, str(exc), "structure")]
    if not isinstance(model, dict):
        return [_issue("schema_invalid", prefix, "embedded model must be a JSON object", "structure")]
    graph = model.get("graph")
    if model.get("schema_version") != "2.0" or not isinstance(graph, dict):
        return [_issue("schema_invalid", prefix, "embedded model does not contain a schema 2.0 graph", "structure")]
    source = scene.get("source", {})
    if graph.get("graph_id") != source.get("graph_id"):
        return [_issue("source_matrix_invalid", prefix + "/graph/graph_id", "embedded model graph_id differs from scene source")]
    raw_nodes = graph.get("nodes")
    if not isinstance(raw_nodes, list):
        return [_issue("schema_invalid", prefix + "/graph/nodes", "embedded model graph nodes must be an array", "structure")]

    issues: list[SceneValidationIssue] = []
    node_map: dict[str, Mapping[str, Any]] = {}
    node_indexes: dict[str, int] = {}
    for index, node in enumerate(raw_nodes):
        node_path = f"{prefix}/graph/nodes/{index}"
        if not isinstance(node, dict):
            issues.append(_issue("schema_invalid", node_path, "model graph node must be an object", "structure"))
            continue
        node_id = node.get("node_id")
        output_count = node.get("output_count")
        inputs = node.get("inputs")
        if (
            not isinstance(node_id, str)
            or not node_id
            or not isinstance(node.get("op"), str)
            or not isinstance(node.get("params"), dict)
            or not isinstance(inputs, list)
            or not all(isinstance(value, str) for value in inputs)
            or isinstance(output_count, bool)
            or not isinstance(output_count, int)
            or output_count < 1
        ):
            issues.append(_issue("schema_invalid", node_path, "model graph node has an invalid Viewer operation shape", "structure"))
            continue
        if node_id in node_map:
            issues.append(_issue("id_duplicate", node_path + "/node_id", "model graph node_id is duplicated"))
            continue
        node_map[node_id] = node
        node_indexes[node_id] = index
        if "source" in node:
            issues.extend(
                _operation_source_issues(
                    node["source"],
                    path=node_path + "/source",
                    source_files=source_files,
                )
            )
    for node_id, node in node_map.items():
        for input_id in node.get("inputs", []):
            if input_id not in node_map:
                issues.append(_issue("reference_missing", f"{prefix}/graph/nodes/{node_indexes[node_id]}/inputs", "model graph input references a missing node"))
    leaf_ids = model.get("leaf_ids")
    if not isinstance(leaf_ids, list) or not all(isinstance(value, str) and value in node_map for value in leaf_ids):
        issues.append(_issue("reference_missing", prefix + "/leaf_ids", "model leaf_ids must resolve to graph nodes"))

    def validate_reference(record: Any, path: str) -> None:
        if not isinstance(record, dict):
            return
        node_id = record.get("node_id")
        output_slot = record.get("output_slot")
        node = node_map.get(node_id) if isinstance(node_id, str) else None
        if (
            node is None
            or isinstance(output_slot, bool)
            or not isinstance(output_slot, int)
            or output_slot < 0
            or output_slot >= node.get("output_count", 0)
        ):
            issues.append(_issue("reference_missing", path, "model source does not resolve to an embedded graph output"))

    for index, definition in enumerate(scene.get("definitions", [])):
        nested = definition.get("source") if isinstance(definition, dict) else None
        if isinstance(nested, dict) and nested.get("kind") in {"product_model", "model_output"}:
            validate_reference(nested, f"/definitions/{index}/source")
    for index, connector in enumerate(scene.get("connectors", [])):
        nested = connector.get("source") if isinstance(connector, dict) else None
        if isinstance(nested, dict) and nested.get("kind") == "model_operation":
            validate_reference(nested, f"/connectors/{index}/source")
    entity_records = {
        record.get("uri"): record
        for record in scene.get("entity_assets", [])
        if isinstance(record, dict)
    }
    for uri, entity_payload in entity_payloads.items():
        if uri not in entity_records:
            continue
        for index, entity in enumerate(entity_payload.get("entities", [])):
            nested = entity.get("source") if isinstance(entity, dict) else None
            if isinstance(nested, dict) and nested.get("kind") in {"model_output", "model_topology"}:
                validate_reference(nested, f"/{uri}/entities/{index}/source")
    return issues


def _embedded_presentation_issues(
    scene: Mapping[str, Any],
    payload: bytes,
    uri: str,
    *,
    limits: SceneResourceLimits,
) -> list[SceneValidationIssue]:
    prefix = f"/{uri}"
    presentation_report = validate_presentation(payload, limits=limits)
    issues = []
    for issue in presentation_report.issues:
        code = (
            "source_matrix_invalid"
            if issue.code == "presentation_reference_invalid"
            else issue.code
        )
        path = "" if _has_root_pointer_policy(code) else prefix + issue.path
        issues.append(_issue(code, path, issue.message, issue.phase))
    if _has_blocking_issues(presentation_report.issues):
        return issues
    try:
        presentation = parse_canonical_json(payload)
    except ValueError:
        return issues
    if not isinstance(presentation, dict):
        return issues

    source = scene.get("presentation_source")
    if not isinstance(source, dict):
        return issues
    if presentation.get("presentation_id") != source.get("presentation_id"):
        issues.append(_issue("source_matrix_invalid", prefix + "/presentation_id", "presentation_id differs from manifest presentation_source"))
    if presentation.get("source_scene_id") != scene.get("scene_id"):
        issues.append(_issue("source_matrix_invalid", prefix + "/source_scene_id", "presentation source_scene_id differs from manifest scene_id"))

    scene_appearances = [
        appearance for appearance in scene.get("appearances", []) if isinstance(appearance, dict)
    ]
    expected_appearance_ids: dict[Any, str] = {}
    for index, authored in enumerate(presentation.get("appearances", [])):
        if not isinstance(authored, dict):
            continue
        name = authored.get("name")
        evaluated = {
            "alpha_mode": authored.get("alpha_mode"),
            "base_color": authored.get("base_color"),
            "double_sided": authored.get("double_sided"),
            "edge_color": authored.get("edge_color"),
            "metallic": authored.get("metallic"),
            "name": name,
            "roughness": authored.get("roughness"),
            "sdk_metadata": {},
            "source": {
                "appearance_name": name,
                "kind": "presentation",
                "presentation_id": presentation.get("presentation_id"),
            },
        }
        appearance_id = "appearance/evaluated/" + hashlib.sha256(
            canonical_json_bytes(evaluated)
        ).hexdigest()
        expected_appearance_ids[name] = appearance_id
        expected = {"appearance_id": appearance_id, **evaluated}
        matches = [appearance for appearance in scene_appearances if appearance == expected]
        if len(matches) != 1:
            issues.append(_issue("source_matrix_invalid", prefix + f"/appearances/{index}", "presentation appearance does not resolve to exactly one evaluated scene appearance"))

    expected_id_set = set(expected_appearance_ids.values())
    for index, appearance in enumerate(scene_appearances):
        appearance_source = appearance.get("source")
        if isinstance(appearance_source, dict) and appearance_source.get("kind") == "presentation" and appearance.get("appearance_id") not in expected_id_set:
            issues.append(_issue("source_matrix_invalid", f"/appearances/{index}/source/appearance_name", "evaluated presentation appearance does not resolve to an authored appearance"))

    scene_nodes = [node for node in scene.get("nodes", []) if isinstance(node, dict)]
    node_map = {node.get("node_id"): node for node in scene_nodes}
    definition_map = {
        definition.get("definition_id"): definition
        for definition in scene.get("definitions", [])
        if isinstance(definition, dict)
    }
    overrides = [
        override for override in presentation.get("node_overrides", []) if isinstance(override, dict)
    ]
    override_map = {override.get("node_id"): override for override in overrides}
    for index, override in enumerate(overrides):
        node = node_map.get(override.get("node_id"))
        if node is None:
            issues.append(_issue("source_matrix_invalid", prefix + f"/node_overrides/{index}/node_id", "node override target does not exist in the scene"))
            continue
        appearance_name = override.get("appearance_name")
        if appearance_name is not None:
            definition = definition_map.get(node.get("definition_id"))
            if not isinstance(definition, dict) or definition.get("kind") not in {"part", "shape"}:
                issues.append(_issue("source_matrix_invalid", prefix + f"/node_overrides/{index}/appearance_name", "appearance override target is not a renderable Part or Shape"))

    for index, node in enumerate(scene_nodes):
        override = override_map.get(node.get("node_id"))
        expected_visible = override.get("visible", True) if isinstance(override, dict) else True
        appearance_name = override.get("appearance_name") if isinstance(override, dict) else None
        expected_appearance_id = expected_appearance_ids.get(appearance_name) if appearance_name is not None else None
        if node.get("visible") != expected_visible:
            issues.append(_issue("source_matrix_invalid", f"/nodes/{index}/visible", "node visibility does not match the embedded presentation"))
        if appearance_name in expected_appearance_ids and node.get("appearance_override_id") != expected_appearance_id:
            issues.append(_issue("source_matrix_invalid", f"/nodes/{index}/appearance_override_id", "node appearance override does not resolve the embedded presentation name"))
        if appearance_name is None and node.get("appearance_override_id") is not None:
            issues.append(_issue("source_matrix_invalid", f"/nodes/{index}/appearance_override_id", "node appearance override is not authored by the embedded presentation"))

    scene_cameras = [camera for camera in scene.get("cameras", []) if isinstance(camera, dict)]
    expected_camera_ids: set[str] = set()
    for index, authored in enumerate(presentation.get("cameras", [])):
        if not isinstance(authored, dict):
            continue
        if authored.get("parent_node_id") is not None and authored.get("parent_node_id") not in node_map:
            issues.append(_issue("source_matrix_invalid", prefix + f"/cameras/{index}/parent_node_id", "presentation camera parent does not exist in the scene"))
        camera_id = f"camera/{presentation.get('presentation_id')}/{_encode_segment(str(authored.get('name', '')))}"
        expected_camera_ids.add(camera_id)
        expected = {"camera_id": camera_id, **authored}
        matches = [camera for camera in scene_cameras if camera == expected]
        if len(matches) != 1:
            issues.append(_issue("source_matrix_invalid", prefix + f"/cameras/{index}", "presentation camera does not resolve to exactly one evaluated scene camera"))
    for index, camera in enumerate(scene_cameras):
        if camera.get("camera_id") not in expected_camera_ids:
            issues.append(_issue("source_matrix_invalid", f"/cameras/{index}", "evaluated scene camera is not authored by the embedded presentation"))
    return issues


def _compute_package_budget_totals(
    *,
    scene_json_bytes: int,
    glb_decoded_buffer_bytes: int,
    entity_json_bytes: int,
    other_immutable_json_bytes: int,
    entity_count: int,
    entity_vertex_count: int,
    triangle_vertex_count: int,
    triangle_count: int,
    line_vertex_count: int,
    line_segment_count: int,
) -> dict[str, int]:
    return {
        "static_decoded_buffer_bytes": (
            scene_json_bytes
            + glb_decoded_buffer_bytes
            + entity_json_bytes
            + other_immutable_json_bytes
            + 2 * entity_vertex_count * 16
        ),
        "entity_count": entity_count,
        "triangle_vertex_total": triangle_vertex_count,
        "triangle_total": triangle_count,
        "line_vertex_total": line_vertex_count,
        "line_segment_total": line_segment_count,
    }


def _package_budget_issues(
    totals: Mapping[str, int], *, limits: Any = BASE_LIMITS
) -> list[SceneValidationIssue]:
    issues: list[SceneValidationIssue] = []
    if totals["static_decoded_buffer_bytes"] > limits.static_decoded_buffer_bytes:
        issues.append(_issue("static_buffer_limit_exceeded", "", "static decoded buffer formula exceeds resource limit", "budget"))
    if totals["entity_count"] > limits.entities_total:
        issues.append(_issue("resource_limit_exceeded", "/entity_assets", "total entity count exceeds resource limit", "budget"))
    for field, limit, message in (
        ("triangle_vertex_total", limits.triangle_vertices_total, "total triangle GLB vertex count exceeds resource limit"),
        ("triangle_total", limits.triangles_total, "total triangle count exceeds resource limit"),
        ("line_vertex_total", limits.line_vertices_total, "total line GLB vertex count exceeds resource limit"),
        ("line_segment_total", limits.line_segments_total, "total line segment count exceeds resource limit"),
    ):
        if totals[field] > limit:
            issues.append(_issue("resource_limit_exceeded", "", message, "budget"))
    return issues


def validate_scene_package(
    scene: Any,
    blobs: Mapping[str, bytes | bytearray | memoryview],
    *,
    limits: SceneResourceLimits = BASE_LIMITS,
) -> SceneValidationReport:
    manifest_report = validate_scene_manifest(scene, limits=limits)
    issues = list(manifest_report.issues)
    parsed, parse_issues = _parse_input(scene, require_canonical=isinstance(scene, (bytes, bytearray, memoryview, str)))
    issues.extend(parse_issues)
    if not isinstance(parsed, dict):
        return _report(issues, artifact="package")
    if _has_blocking_issues(issues):
        return _report(issues, artifact="package")
    records, record_issues = _package_reference_records(parsed)
    issues.extend(record_issues)
    if set(blobs) != set(records):
        issues.append(_issue("package_member_set_invalid", "", "blob keys do not exactly equal manifest URI references", "package"))
    glb_info: dict[str, GlbInfo] = {}
    entity_payloads: dict[str, Mapping[str, Any]] = {}
    embedded_model: bytes | None = None
    source_files: dict[str, str] = {}
    source_path_by_uri = {
        record.get("uri"): record.get("path")
        for record in parsed.get("source", {}).get("source_files", [])
        if isinstance(record, dict)
    }
    budget = {
        "scene_json_bytes": len(canonical_json_bytes(parsed)),
        "glb_decoded_buffer_bytes": 0,
        "entity_json_bytes": 0,
        "other_immutable_json_bytes": 0,
        "entity_count": 0,
        "entity_vertex_count": 0,
        "triangle_vertex_count": 0,
        "triangle_count": 0,
        "line_vertex_count": 0,
        "line_segment_count": 0,
    }
    for uri, record in records.items():
        if uri not in blobs:
            continue
        blob = blobs[uri]
        payload_size = blob.nbytes if isinstance(blob, memoryview) else len(blob)
        role_limit = {
            "entity": limits.entity_json_bytes,
            "model_source": limits.model_json_bytes,
            "presentation": limits.presentation_json_bytes,
        }.get(record.get("media_role"), limits.one_member_bytes)
        if payload_size > min(limits.one_member_bytes, role_limit):
            issues.append(_issue("resource_limit_exceeded", f"/{uri}", "package member bytes exceed resource limit", "budget"))
            continue
        payload = bytes(blob)
        if len(payload) != record.get("byte_length"):
            issues.append(_issue("blob_length_mismatch", f"/{uri}", "blob length differs from manifest", "package"))
        digest = "sha256:" + hashlib.sha256(payload).hexdigest()
        if digest != record.get("content_hash"):
            issues.append(_issue("blob_hash_mismatch", f"/{uri}", "blob hash differs from manifest", "package"))
        media_role = record.get("media_role")
        if media_role in {"geometry", "edge"}:
            try:
                info = preflight_glb(payload, expected_kind="triangle" if media_role == "geometry" else "line", limits=limits)
                glb_info[uri] = info
                budget["glb_decoded_buffer_bytes"] += info.decoded_buffer_bytes
                if info.kind == "triangle":
                    budget["triangle_vertex_count"] += info.vertex_count
                    budget["triangle_count"] += info.primitive_count
                else:
                    budget["line_vertex_count"] += info.vertex_count
                    budget["line_segment_count"] += info.primitive_count
            except ValueError as exc:
                issues.append(_issue("glb_profile_invalid", f"/{uri}", str(exc), "package"))
        elif media_role == "entity":
            entity_report = validate_entity_asset(payload, limits=limits)
            issues.extend(
                _issue(
                    issue.code,
                    "" if _has_root_pointer_policy(issue.code) else f"/{uri}" + issue.path,
                    issue.message,
                    issue.phase,
                )
                for issue in entity_report.issues
            )
            try:
                entity_payload = parse_canonical_json(payload)
                if isinstance(entity_payload, dict):
                    entity_payloads[uri] = entity_payload
                    budget["entity_json_bytes"] += len(payload)
                    entities = entity_payload.get("entities", [])
                    entities = entities if isinstance(entities, list) else []
                    budget["entity_count"] += len(entities)
                    vertex_count = sum(1 for entity in entities if isinstance(entity, dict) and entity.get("kind") == "vertex")
                    budget["entity_vertex_count"] += vertex_count
            except ValueError:
                pass
        elif media_role == "presentation":
            issues.extend(
                _embedded_presentation_issues(
                    parsed, payload, uri, limits=limits
                )
            )
            budget["other_immutable_json_bytes"] += len(payload)
        elif media_role == "model_source":
            embedded_model = payload
            budget["other_immutable_json_bytes"] += len(payload)
        elif media_role == "python_source":
            try:
                source_text = payload.decode("utf-8", errors="strict")
            except UnicodeDecodeError as exc:
                issues.append(_issue("invalid_utf8", f"/{uri}", str(exc), "parse"))
            else:
                source_path = source_path_by_uri.get(uri)
                if isinstance(source_path, str):
                    source_files[source_path] = source_text
            budget["other_immutable_json_bytes"] += len(payload)
    if embedded_model is not None:
        issues.extend(
            _embedded_model_issues(
                parsed,
                embedded_model,
                source_files=source_files,
                entity_payloads=entity_payloads,
            )
        )
    issues.extend(_package_budget_issues(_compute_package_budget_totals(**budget), limits=limits))

    geometry_records = {record.get("asset_id"): record for record in parsed.get("geometry_assets", []) if isinstance(record, dict)}
    edge_records = {record.get("asset_id"): record for record in parsed.get("edge_assets", []) if isinstance(record, dict)}
    for index, definition in enumerate(parsed.get("definitions", [])):
        if not isinstance(definition, dict) or definition.get("kind") == "assembly":
            continue
        entity_record = next((record for record in parsed.get("entity_assets", []) if isinstance(record, dict) and record.get("entity_asset_id") == definition.get("entity_asset_id")), None)
        if not isinstance(entity_record, dict):
            continue
        payload = entity_payloads.get(entity_record.get("uri"))
        geometry_record = geometry_records.get(definition.get("geometry_asset_id"))
        edge_record = edge_records.get(definition.get("edge_asset_id"))
        geometry = glb_info.get(geometry_record.get("uri")) if isinstance(geometry_record, dict) else None
        edge = glb_info.get(edge_record.get("uri")) if isinstance(edge_record, dict) else None
        for record, info in ((geometry_record, geometry), (edge_record, edge)):
            if isinstance(record, dict) and info is not None:
                glb_minimum, glb_maximum = info.position_bounds
                expected_bounds = {
                    "min": [1000 * glb_minimum[0], -1000 * glb_maximum[2], 1000 * glb_minimum[1]],
                    "max": [1000 * glb_maximum[0], -1000 * glb_minimum[2], 1000 * glb_maximum[1]],
                }
                if record.get("scene_local_bounds") != expected_bounds:
                    issues.append(_issue("bounds_invalid", f"/definitions/{index}", "asset scene_local_bounds differ from transformed GLB bounds"))
        if isinstance(payload, dict):
            if payload.get("definition_id") != definition.get("definition_id") or payload.get("geometry_asset_id") != definition.get("geometry_asset_id") or payload.get("edge_asset_id") != definition.get("edge_asset_id"):
                issues.append(_issue("reference_missing", f"/definitions/{index}/entity_asset_id", "entity sidecar ownership triple differs from definition"))
            if payload.get("geometry_engine", {}).get("version") != parsed.get("generator", {}).get("ocp_version"):
                issues.append(_issue("source_matrix_invalid", f"/definitions/{index}/entity_asset_id", "entity geometry engine version differs from manifest generator"))
            scene_source_kind = parsed.get("source", {}).get("kind")
            allowed_entity_sources = {
                "model": {"model_output", "model_topology"},
                "imported": {"imported_primitive", "unbound"},
                "manual": {"unbound"},
            }.get(scene_source_kind, set())
            for entity_index, entity in enumerate(payload.get("entities", [])):
                if not isinstance(entity, dict):
                    continue
                entity_path = f"/{entity_record.get('uri')}/entities/{entity_index}"
                entity_source = entity.get("source", {})
                if not isinstance(entity_source, dict) or entity_source.get("kind") not in allowed_entity_sources:
                    issues.append(_issue("source_matrix_invalid", entity_path + "/source", "entity source is incompatible with scene source"))
                elif scene_source_kind == "model":
                    definition_source = definition.get("source", {})
                    if any(
                        entity_source.get(field) != definition_source.get(field)
                        for field in ("graph_id", "node_id", "output_slot")
                    ):
                        issues.append(_issue("source_matrix_invalid", entity_path + "/source", "entity model source differs from owning definition output"))
                if entity.get("kind") == "solid":
                    expected_status = "not_applicable"
                elif definition.get("kind") != "part":
                    expected_status = "owner_not_part"
                elif scene_source_kind != "model":
                    expected_status = "source_not_model"
                elif entity.get("sdk_connector_frame") is None:
                    expected_status = "frame_undefined"
                else:
                    expected_status = None
                if expected_status is not None and entity.get("connector_binding_status") != expected_status:
                    issues.append(_issue("connector_invalid", entity_path + "/connector_binding_status", f"connector binding status must be {expected_status}"))
            face_total = sum(group.get("index_count", 0) for group in payload.get("face_groups", []) if isinstance(group, dict))
            edge_total = sum(group.get("index_count", 0) for group in payload.get("edge_groups", []) if isinstance(group, dict))
            if geometry is not None and face_total != geometry.index_count:
                issues.append(_issue("entity_range_invalid", f"/definitions/{index}/entity_asset_id", "face groups do not partition triangle GLB indices"))
            if edge is not None and edge_total != edge.index_count:
                issues.append(_issue("entity_range_invalid", f"/definitions/{index}/entity_asset_id", "edge groups do not partition line GLB indices"))
    return _report(issues, artifact="package")


def _assert(report: SceneValidationReport) -> None:
    if not report.valid:
        raise SceneContractError(report)


def assert_scene_manifest(scene: Any) -> None:
    _assert(validate_scene_manifest(scene))


def assert_entity_asset(asset: Any) -> None:
    _assert(validate_entity_asset(asset))


def assert_presentation(value: Any) -> None:
    _assert(validate_presentation(value))


def assert_connector_binding(value: Any) -> None:
    _assert(validate_connector_binding(value))


def assert_normalized_product(value: Any) -> None:
    _assert(validate_normalized_product(value))


def assert_scene_package(scene: Any, blobs: Mapping[str, bytes | bytearray | memoryview]) -> None:
    _assert(validate_scene_package(scene, blobs))


_rule_registry()
