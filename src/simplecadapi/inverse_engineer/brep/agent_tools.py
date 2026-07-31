"""Framework-neutral tool registry for iterative STEP reconstruction agents."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError

from .compare import compare_steps
from .diagnostics import (
    build_difference_regions,
    compare_boundary_distance,
    compare_entities,
    compare_global_properties,
    compare_sections,
    compute_material_difference,
    evaluate_result,
    find_nearby_entities,
)
from .model import get_model_summary, inspect_entity
from .queries import (
    extract_face_boundaries,
    get_topology_neighborhood,
    make_section,
    measure_relation,
    probe_point,
)
from .render import render_region


class BRepToolError(ValueError):
    """Raised when a framework-neutral BREP tool call is malformed."""


@dataclass(frozen=True)
class AgentTool:
    name: str
    description: str
    parameters: dict[str, Any]
    handler: Callable[[Mapping[str, Any]], Any]

    def schema(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": deepcopy(self.parameters),
            },
        }


def _object_schema(
    properties: Mapping[str, Any],
    required: tuple[str, ...],
) -> dict[str, Any]:
    return {
        "type": "object",
        "properties": dict(properties),
        "required": list(required),
        "additionalProperties": False,
    }


_PATH = {"type": "string", "description": "Local .step or .stp path."}
_ENTITY = {
    "type": "string",
    "description": "Stable zero-based id such as face:12, edge:4, or vertex:8.",
}
_POINT = {
    "type": "array",
    "items": {"type": "number"},
    "minItems": 3,
    "maxItems": 3,
}
_ENTITY_TYPES = {
    "type": "array",
    "items": {"type": "string", "enum": ["face", "edge", "vertex"]},
}


def _require(arguments: Mapping[str, Any], name: str) -> Any:
    if name not in arguments:
        raise BRepToolError(f"Missing required tool argument: {name}")
    return arguments[name]


def _boolean(
    arguments: Mapping[str, Any],
    name: str,
    *,
    default: bool | None = None,
) -> bool:
    value = arguments.get(name, default)
    if type(value) is not bool:
        raise BRepToolError(f"Tool argument {name} must be a JSON boolean")
    return value


def _summary(arguments: Mapping[str, Any]) -> Any:
    return get_model_summary(
        _require(arguments, "model_path"),
        include_parameter_groups=_boolean(
            arguments,
            "include_parameter_groups",
            default=False,
        ),
        max_parameter_groups=int(arguments.get("max_parameter_groups", 24)),
        examples_per_group=int(arguments.get("examples_per_group", 3)),
    )


def _inspect(arguments: Mapping[str, Any]) -> Any:
    return inspect_entity(
        _require(arguments, "model_path"),
        _require(arguments, "entity_id"),
        include_curve_definition=_boolean(
            arguments,
            "include_curve_definition",
            default=False,
        ),
        include_surface_definition=_boolean(
            arguments,
            "include_surface_definition",
            default=False,
        ),
        max_surface_control_points=int(
            arguments.get("max_surface_control_points", 256)
        ),
    )


def _neighborhood(arguments: Mapping[str, Any]) -> Any:
    return get_topology_neighborhood(
        _require(arguments, "model_path"),
        _require(arguments, "entity_id"),
        depth=int(arguments.get("depth", 1)),
        max_entities=int(arguments.get("max_entities", 100)),
    )


def _relation(arguments: Mapping[str, Any]) -> Any:
    return measure_relation(
        _require(arguments, "model_path"),
        _require(arguments, "first_entity_id"),
        _require(arguments, "second_entity_id"),
        tolerance=float(arguments.get("tolerance", 1.0e-7)),
        angular_tolerance_degrees=float(
            arguments.get("angular_tolerance_degrees", 1.0e-4)
        ),
        second_model_or_path=arguments.get("second_model_path"),
    )


def _section(arguments: Mapping[str, Any]) -> Any:
    connection_tolerance = arguments.get("connection_tolerance")
    return make_section(
        _require(arguments, "model_path"),
        _require(arguments, "origin"),
        _require(arguments, "normal"),
        tolerance=float(arguments.get("tolerance", 1.0e-7)),
        samples_per_edge=int(arguments.get("samples_per_edge", 16)),
        connection_tolerance=(
            float(connection_tolerance) if connection_tolerance is not None else None
        ),
        compact=_boolean(arguments, "compact", default=False),
    )


def _boundaries(arguments: Mapping[str, Any]) -> Any:
    return extract_face_boundaries(
        _require(arguments, "model_path"),
        _require(arguments, "face_id"),
        samples_per_edge=int(arguments.get("samples_per_edge", 16)),
        compact=_boolean(arguments, "compact", default=False),
        include_curve_definitions=_boolean(
            arguments,
            "include_curve_definitions",
            default=False,
        ),
        curve_definition_edge_ids=arguments.get("curve_definition_edge_ids"),
        max_total_control_points=int(arguments.get("max_total_control_points", 256)),
    )


def _probe(arguments: Mapping[str, Any]) -> Any:
    return probe_point(
        _require(arguments, "model_path"),
        _require(arguments, "point"),
        entity_kinds=tuple(arguments.get("entity_kinds", ("face", "edge", "vertex"))),
        limit=int(arguments.get("limit", 20)),
    )


def _render(arguments: Mapping[str, Any]) -> Any:
    return {
        "output_path": str(
            render_region(
                _require(arguments, "model_path"),
                _require(arguments, "entity_ids"),
                _require(arguments, "output_path"),
                neighborhood_depth=int(arguments.get("neighborhood_depth", 0)),
            )
        )
    }


def _global(arguments: Mapping[str, Any]) -> Any:
    return compare_global_properties(
        _require(arguments, "target_path"),
        _require(arguments, "current_path"),
    )


def _boundary(arguments: Mapping[str, Any]) -> Any:
    return compare_boundary_distance(
        _require(arguments, "target_path"),
        _require(arguments, "current_path"),
        linear_deflection=float(arguments.get("linear_deflection", 0.5)),
        max_samples=int(arguments.get("max_samples", 200)),
        target_face_ids=arguments.get("target_face_ids"),
        current_face_ids=arguments.get("current_face_ids"),
        include_records=_boolean(arguments, "include_records", default=False),
    )


def _material(arguments: Mapping[str, Any]) -> Any:
    output_directory = arguments.get("output_directory")
    return compute_material_difference(
        _require(arguments, "target_path"),
        _require(arguments, "current_path"),
        boolean_tolerance=arguments.get("boolean_tolerance"),
        output_directory=output_directory,
        include_components=_boolean(
            arguments,
            "include_components",
            default=output_directory is not None,
        ),
    )


def _compare_sections(arguments: Mapping[str, Any]) -> Any:
    return compare_sections(
        _require(arguments, "target_path"),
        _require(arguments, "current_path"),
        _require(arguments, "origin"),
        _require(arguments, "normal"),
        tolerance=float(arguments.get("tolerance", 1.0e-7)),
        samples_per_edge=int(arguments.get("samples_per_edge", 32)),
    )


def _regions(arguments: Mapping[str, Any]) -> Any:
    return build_difference_regions(
        _require(arguments, "target_path"),
        _require(arguments, "current_path"),
        distance_threshold=float(arguments.get("distance_threshold", 0.1)),
        linear_deflection=float(arguments.get("linear_deflection", 0.5)),
        max_samples=int(arguments.get("max_samples", 600)),
        cluster_radius=arguments.get("cluster_radius"),
        merge_radius=arguments.get("merge_radius"),
        boolean_tolerance=arguments.get("boolean_tolerance"),
        include_boundary=_boolean(arguments, "include_boundary", default=False),
        boundary_result=arguments.get("boundary_result"),
        material_result=arguments.get("material_result"),
    )


def _nearby(arguments: Mapping[str, Any]) -> Any:
    return find_nearby_entities(
        _require(arguments, "model_path"),
        location=arguments.get("location"),
        region=arguments.get("region"),
        radius=float(arguments.get("radius", 1.0)),
        entity_types=tuple(arguments.get("entity_types", ("face", "edge", "vertex"))),
        max_results=int(arguments.get("max_results", 30)),
    )


def _entities(arguments: Mapping[str, Any]) -> Any:
    return compare_entities(
        _require(arguments, "target_path"),
        _require(arguments, "target_entity_id"),
        _require(arguments, "current_path"),
        _require(arguments, "current_entity_id"),
    )


def _evaluate(arguments: Mapping[str, Any]) -> Any:
    return evaluate_result(
        _require(arguments, "target_path"),
        _require(arguments, "current_path"),
        replay_succeeded=_boolean(arguments, "replay_succeeded"),
        boundary_tolerance=float(arguments.get("boundary_tolerance", 0.1)),
        bounding_box_tolerance=float(arguments.get("bounding_box_tolerance", 0.1)),
        relative_volume_tolerance=float(
            arguments.get("relative_volume_tolerance", 1.0e-3)
        ),
        relative_area_tolerance=float(arguments.get("relative_area_tolerance", 1.0e-3)),
        relative_material_tolerance=float(
            arguments.get("relative_material_tolerance", 1.0e-3)
        ),
        linear_deflection=float(arguments.get("linear_deflection", 0.5)),
        max_samples=int(arguments.get("max_samples", 600)),
        boolean_tolerance=arguments.get("boolean_tolerance"),
        require_strict_brep=_boolean(
            arguments,
            "require_strict_brep",
            default=False,
        ),
    )


def _strict(arguments: Mapping[str, Any]) -> Any:
    return compare_steps(
        _require(arguments, "target_path"),
        _require(arguments, "current_path"),
        geometric_tolerance=float(arguments.get("geometric_tolerance", 1.0e-7)),
        boolean_volume_tolerance=float(
            arguments.get("boolean_volume_tolerance", 1.0e-9)
        ),
    ).to_dict()


_COMMON_PAIR_PROPERTIES = {
    "target_path": _PATH,
    "current_path": _PATH,
}
_TOOLS = (
    AgentTool(
        "get_model_summary",
        "Get global facts and optional bounded carrier, canonical-axis, and adjacency-signature groups; groups do not prove a pattern.",
        _object_schema(
            {
                "model_path": _PATH,
                "include_parameter_groups": {
                    "type": "boolean",
                    "description": "Include bounded carrier, axis, and adjacency-signature groups.",
                },
                "max_parameter_groups": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Maximum groups returned per category.",
                },
                "examples_per_group": {"type": "integer", "minimum": 1},
            },
            ("model_path",),
        ),
        _summary,
    ),
    AgentTool(
        "inspect_entity",
        "Inspect one stable entity, with optional exact B-spline/Bezier curve data or a bounded untrimmed surface-carrier definition.",
        _object_schema(
            {
                "model_path": _PATH,
                "entity_id": _ENTITY,
                "include_curve_definition": {"type": "boolean"},
                "include_surface_definition": {"type": "boolean"},
                "max_surface_control_points": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 256,
                },
            },
            ("model_path", "entity_id"),
        ),
        _inspect,
    ),
    AgentTool(
        "get_topology_neighborhood",
        "Expand a bounded local Face-Edge-Vertex topology neighborhood.",
        _object_schema(
            {
                "model_path": _PATH,
                "entity_id": _ENTITY,
                "depth": {"type": "integer", "minimum": 0, "default": 1},
                "max_entities": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 100,
                },
            },
            ("model_path", "entity_id"),
        ),
        _neighborhood,
    ),
    AgentTool(
        "measure_relation",
        "Measure exact distance and supported parallel, coplanar, coaxial, concentric, perpendicular, touching, and tangent relations.",
        _object_schema(
            {
                "model_path": _PATH,
                "second_model_path": _PATH,
                "first_entity_id": _ENTITY,
                "second_entity_id": _ENTITY,
                "tolerance": {"type": "number", "exclusiveMinimum": 0},
                "angular_tolerance_degrees": {
                    "type": "number",
                    "minimum": 0,
                },
            },
            ("model_path", "first_entity_id", "second_entity_id"),
        ),
        _relation,
    ),
    AgentTool(
        "make_section",
        "Intersect a model with a plane; compact mode omits sampled arrays while retaining contour evidence.",
        _object_schema(
            {
                "model_path": _PATH,
                "origin": _POINT,
                "normal": _POINT,
                "tolerance": {"type": "number", "exclusiveMinimum": 0},
                "connection_tolerance": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                },
                "samples_per_edge": {"type": "integer", "minimum": 4},
                "compact": {"type": "boolean"},
            },
            ("model_path", "origin", "normal"),
        ),
        _section,
    ),
    AgentTool(
        "extract_face_boundaries",
        "Extract ordered face loops; compact mode can return stable-ID-sorted exact definitions for supported selected curves.",
        _object_schema(
            {
                "model_path": _PATH,
                "face_id": _ENTITY,
                "samples_per_edge": {"type": "integer", "minimum": 2},
                "compact": {"type": "boolean"},
                "include_curve_definitions": {"type": "boolean"},
                "curve_definition_edge_ids": {
                    "type": "array",
                    "items": _ENTITY,
                    "uniqueItems": True,
                },
                "max_total_control_points": {
                    "type": "integer",
                    "minimum": 1,
                    "default": 256,
                },
            },
            ("model_path", "face_id"),
        ),
        _boundaries,
    ),
    AgentTool(
        "probe_point",
        "Find exact nearest faces, edges, and vertices to a spatial point.",
        _object_schema(
            {
                "model_path": _PATH,
                "point": _POINT,
                "entity_kinds": _ENTITY_TYPES,
                "limit": {"type": "integer", "minimum": 1},
            },
            ("model_path", "point"),
        ),
        _probe,
    ),
    AgentTool(
        "render_region",
        "Highlight stable entities and render synchronized model views.",
        _object_schema(
            {
                "model_path": _PATH,
                "entity_ids": {"type": "array", "items": _ENTITY, "minItems": 1},
                "output_path": {"type": "string"},
                "neighborhood_depth": {"type": "integer", "minimum": 0},
            },
            ("model_path", "entity_ids", "output_path"),
        ),
        _render,
    ),
    AgentTool(
        "compare_global_properties",
        "Compare body counts, bounds, volume, area, centroid, and topology counts.",
        _object_schema(_COMMON_PAIR_PROPERTIES, ("target_path", "current_path")),
        _global,
    ),
    AgentTool(
        "compare_boundary_distance",
        "Compute bidirectional sampled-boundary to exact-boundary distances.",
        _object_schema(
            {
                **_COMMON_PAIR_PROPERTIES,
                "linear_deflection": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                },
                "max_samples": {"type": "integer", "minimum": 16},
                "target_face_ids": {
                    "type": "array",
                    "items": _ENTITY,
                    "minItems": 1,
                },
                "current_face_ids": {
                    "type": "array",
                    "items": _ENTITY,
                    "minItems": 1,
                },
                "include_records": {"type": "boolean"},
            },
            ("target_path", "current_path"),
        ),
        _boundary,
    ),
    AgentTool(
        "compute_material_difference",
        "Estimate missing/excess volumes with one intersection, or build "
        "directional-cut components for strict checks, regions, and export.",
        _object_schema(
            {
                **_COMMON_PAIR_PROPERTIES,
                "boolean_tolerance": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                    "description": (
                        "Optional fuzzy tolerance for diagnostics; fuzzy results "
                        "cannot prove strict material equality."
                    ),
                },
                "output_directory": {"type": "string"},
                "include_components": {
                    "type": "boolean",
                    "description": (
                        "Build slower bidirectional difference components; "
                        "required for strict material checks, region diagnostics, "
                        "or STEP export."
                    ),
                },
            },
            ("target_path", "current_path"),
        ),
        _material,
    ),
    AgentTool(
        "compare_sections",
        "Compare target/current contours on the same physical plane.",
        _object_schema(
            {
                **_COMMON_PAIR_PROPERTIES,
                "origin": _POINT,
                "normal": _POINT,
                "tolerance": {"type": "number", "exclusiveMinimum": 0},
                "samples_per_edge": {"type": "integer", "minimum": 4},
            },
            ("target_path", "current_path", "origin", "normal"),
        ),
        _compare_sections,
    ),
    AgentTool(
        "build_difference_regions",
        "Rank Boolean material regions; optionally add expensive boundary anomaly clustering.",
        _object_schema(
            {
                **_COMMON_PAIR_PROPERTIES,
                "distance_threshold": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                },
                "linear_deflection": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                },
                "max_samples": {"type": "integer", "minimum": 16},
                "cluster_radius": {"type": "number", "exclusiveMinimum": 0},
                "merge_radius": {"type": "number", "exclusiveMinimum": 0},
                "boolean_tolerance": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                },
                "include_boundary": {"type": "boolean"},
                "boundary_result": {"type": "object"},
                "material_result": {"type": "object"},
            },
            ("target_path", "current_path"),
        ),
        _regions,
    ),
    AgentTool(
        "find_nearby_entities",
        "Find stable entities near one point or difference-region object.",
        _object_schema(
            {
                "model_path": _PATH,
                "location": _POINT,
                "region": {"type": "object"},
                "radius": {"type": "number", "minimum": 0},
                "entity_types": _ENTITY_TYPES,
                "max_results": {"type": "integer", "minimum": 1},
            },
            ("model_path",),
        ),
        _nearby,
    ),
    AgentTool(
        "compare_entities",
        "Compare two local entities by type, parameters, distance, and adjacency.",
        _object_schema(
            {
                **_COMMON_PAIR_PROPERTIES,
                "target_entity_id": _ENTITY,
                "current_entity_id": _ENTITY,
            },
            (
                "target_path",
                "target_entity_id",
                "current_path",
                "current_entity_id",
            ),
        ),
        _entities,
    ),
    AgentTool(
        "evaluate_result",
        "Apply replay, validity, material, boundary, and optional strict BREP gates.",
        _object_schema(
            {
                **_COMMON_PAIR_PROPERTIES,
                "replay_succeeded": {"type": "boolean"},
                "boundary_tolerance": {"type": "number", "minimum": 0},
                "bounding_box_tolerance": {"type": "number", "minimum": 0},
                "relative_volume_tolerance": {"type": "number", "minimum": 0},
                "relative_area_tolerance": {"type": "number", "minimum": 0},
                "relative_material_tolerance": {"type": "number", "minimum": 0},
                "linear_deflection": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                },
                "max_samples": {"type": "integer", "minimum": 16},
                "boolean_tolerance": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                },
                "require_strict_brep": {"type": "boolean"},
            },
            ("target_path", "current_path", "replay_succeeded"),
        ),
        _evaluate,
    ),
    AgentTool(
        "compare_brep_strict",
        "Compare Boolean material point sets and geometry-labelled incidence topology.",
        _object_schema(
            {
                **_COMMON_PAIR_PROPERTIES,
                "geometric_tolerance": {
                    "type": "number",
                    "exclusiveMinimum": 0,
                },
                "boolean_volume_tolerance": {
                    "type": "number",
                    "minimum": 0,
                },
            },
            ("target_path", "current_path"),
        ),
        _strict,
    ),
)

AGENT_TOOL_NAMES = tuple(tool.name for tool in _TOOLS)
_TOOL_BY_NAME = {tool.name: tool for tool in _TOOLS}


def agent_tool_schemas() -> list[dict[str, Any]]:
    """Return OpenAI-compatible function schemas without framework dependencies."""

    return [tool.schema() for tool in _TOOLS]


def call_agent_tool(name: str, arguments: Mapping[str, Any]) -> Any:
    """Validate and dispatch one tool call by stable public name."""

    if name not in _TOOL_BY_NAME:
        raise BRepToolError(
            f"Unknown BREP tool {name!r}; available tools: "
            f"{', '.join(AGENT_TOOL_NAMES)}"
        )
    if not isinstance(arguments, Mapping):
        raise BRepToolError("Tool arguments must be a mapping")
    tool = _TOOL_BY_NAME[name]
    try:
        Draft202012Validator(tool.parameters).validate(dict(arguments))
    except ValidationError as error:
        location = ".".join(str(item) for item in error.absolute_path)
        prefix = f"{location}: " if location else ""
        raise BRepToolError(
            f"Invalid arguments for {name}: {prefix}{error.message}"
        ) from error
    result = tool.handler(arguments)
    if isinstance(result, Path):
        return str(result)
    if hasattr(result, "to_dict"):
        return result.to_dict()
    return result


__all__ = [
    "AGENT_TOOL_NAMES",
    "AgentTool",
    "BRepToolError",
    "agent_tool_schemas",
    "call_agent_tool",
]
