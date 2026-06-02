"""Graph serialization and replay executor.

Provides:
- ``export_graph_json`` / ``import_graph_json`` for JSON round-trip
- ``replay_graph`` for rebuilding a model from a recorded graph

Usage::

    from simplecadapi.serializer import export_graph_json, import_graph_json, replay_graph

    # Serialize
    json_str = export_graph_json(session.graph)

    # Deserialize
    graph = import_graph_json(json_str)

    # Rebuild
    solids = replay_graph(graph)
"""

from __future__ import annotations

import math
from contextlib import nullcontext

from typing import Any, Dict, List, Optional, Sequence, Tuple, cast

from .errors import raise_harness_error

from .core import AnyShape, Edge, Face, Solid, Vertex, Wire, use_coordinate_system
from .graph import attach_graph_node, suspend_graph_recording
from .ql import selector_from_dict
from .topology import (
    OperationGraph,
    semantic_delta_to_dict,
    topo_delta_to_dict,
    topo_ref_from_dict,
)
from . import operations as ops
from .kernel.ocp_properties import bounding_box


MODEL_SCHEMA_VERSION = "2.0"
CANONICAL_CONTRACT_VERSION = "2.0"


PUBLIC_API_COVERAGE: Dict[str, Dict[str, str]] = {
    # Core geometry ops that are recorded and replayable
    "make_point_rvertex": {"status": "replayable", "op": "make_point_rvertex"},
    "make_line_redge": {"status": "replayable", "op": "make_line_redge"},
    "make_segment_redge": {"status": "expanded_macro", "op": "make_line_redge"},
    "make_segment_rwire": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into make_line_redge + make_wire_from_edges_rwire.",
    },
    "make_circle_redge": {"status": "replayable", "op": "make_circle_redge"},
    "make_circle_rwire": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into make_circle_redge + make_wire_from_edges_rwire.",
    },
    "make_circle_rface": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into edge/wire/face low-level operations.",
    },
    "make_rectangle_rwire": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into make_line_redge + make_wire_from_edges_rwire.",
    },
    "make_rectangle_rface": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into low-level line/wire/face operations.",
    },
    "make_face_from_wire_rface": {"status": "replayable", "op": "make_face_from_wire_rface"},
    "make_wire_from_edges_rwire": {
        "status": "replayable",
        "op": "make_wire_from_edges_rwire",
    },
    "make_box_rsolid": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into low-level sketch + make_extrude_rsolid operations.",
    },
    "make_cylinder_rsolid": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into low-level circle/face + make_extrude_rsolid operations.",
    },
    "make_cone_rsolid": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into low-level profile + make_revolve_rsolid operations.",
    },
    "make_sphere_rsolid": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into low-level profile + make_revolve_rsolid operations.",
    },
    "make_three_point_arc_redge": {
        "status": "replayable",
        "op": "make_three_point_arc_redge",
    },
    "make_three_point_arc_rwire": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into make_three_point_arc_redge + make_wire_from_edges_rwire.",
    },
    "make_angle_arc_redge": {"status": "replayable", "op": "make_angle_arc_redge"},
    "make_angle_arc_rwire": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into make_angle_arc_redge + make_wire_from_edges_rwire.",
    },
    "make_spline_redge": {"status": "replayable", "op": "make_spline_redge"},
    "make_spline_rwire": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into make_spline_redge + make_wire_from_edges_rwire when open.",
    },
    "make_polyline_rwire": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into make_line_redge + make_wire_from_edges_rwire.",
    },
    "make_helix_redge": {"status": "replayable", "op": "make_helix_redge"},
    "make_helix_rwire": {
        "status": "macro",
        "reason": "Composite convenience API that should lower into make_helix_redge + make_wire_from_edges_rwire.",
    },
    "translate_shape": {"status": "replayable", "op": "make_translate_rshape"},
    "rotate_shape": {"status": "replayable", "op": "make_rotate_rshape"},
    "mirror_shape": {"status": "replayable", "op": "make_mirror_rshape"},
    "extrude_rsolid": {"status": "replayable", "op": "make_extrude_rsolid"},
    "revolve_rsolid": {"status": "replayable", "op": "make_revolve_rsolid"},
    "loft_rsolid": {"status": "replayable", "op": "make_loft_rsolid"},
    "sweep_rsolid": {"status": "replayable", "op": "make_sweep_rsolid"},
    "helical_sweep_rsolid": {
        "status": "expanded_macro",
        "op": "make_sweep_rsolid",
        "reason": "Recorded as make_helix_wire + sweep macro instead of a dedicated core IR node.",
    },
    "union_rsolid": {"status": "replayable", "op": "make_union_rsolid"},
    "cut_rsolidlist": {"status": "replayable", "op": "make_cut_rsolidlist"},
    "intersect_rsolidlist": {"status": "replayable", "op": "make_intersect_rsolidlist"},
    "fillet_rsolid": {"status": "replayable", "op": "make_fillet_rsolid"},
    "chamfer_rsolid": {"status": "replayable", "op": "make_chamfer_rsolid"},
    "shell_rsolid": {"status": "replayable", "op": "make_shell_rsolid"},
    "make_select_rvertex": {"status": "replayable", "op": "make_select_rvertex"},
    "make_select_redge": {"status": "replayable", "op": "make_select_redge"},
    "make_select_rwire": {"status": "replayable", "op": "make_select_rwire"},
    "make_select_rface": {"status": "replayable", "op": "make_select_rface"},
    "make_select_rsolid": {"status": "replayable", "op": "make_select_rsolid"},
    "linear_pattern_rsolidlist": {
        "status": "macro",
        "reason": "Pattern convenience API that should lower into repeated make_translate_rshape nodes.",
    },
    "radial_pattern_rsolidlist": {
        "status": "macro",
        "reason": "Pattern convenience API that should lower into repeated make_rotate_rshape nodes.",
    },
    # Explicit gaps / separate systems
    "make_n_hole_flange_rsolid": {
        "status": "macro",
        "reason": "Expanded evolve macro is not serialized as a stable user-level node yet.",
    },
    "make_naca_propeller_blade_rsolid": {
        "status": "macro",
        "reason": "Expanded evolve macro is not serialized as a stable user-level node yet.",
    },
    "make_threaded_rod_rsolid": {
        "status": "macro",
        "reason": "Expanded evolve macro is not serialized as a stable user-level node yet.",
    },
}


CANONICAL_CORE_OP_SET: Tuple[str, ...] = (
    "make_point_rvertex",
    "make_line_redge",
    "make_circle_redge",
    "make_three_point_arc_redge",
    "make_angle_arc_redge",
    "make_spline_redge",
    "make_helix_redge",
    "make_wire_from_edges_rwire",
    "make_face_from_wire_rface",
    "make_extrude_rsolid",
    "make_revolve_rsolid",
    "make_loft_rsolid",
    "make_sweep_rsolid",
    "make_translate_rshape",
    "make_rotate_rshape",
    "make_mirror_rshape",
    "make_cut_rsolidlist",
    "make_union_rsolid",
    "make_intersect_rsolidlist",
    "make_fillet_rsolid",
    "make_chamfer_rsolid",
    "make_shell_rsolid",
    "make_select_rvertex",
    "make_select_redge",
    "make_select_rwire",
    "make_select_rface",
    "make_select_rsolid",
)

SELECTION_REF_SCHEMA: Dict[str, Any] = {
    "edge_param": "selected_edges",
    "face_param": "selected_faces",
    "edge_index_param": "selected_edge_indices",
    "face_index_param": "selected_face_indices",
    "required_topo_ref_fields": [
        "graph_id",
        "node_id",
        "output_slot",
        "kind",
        "topo_id",
    ],
    "optional_fields": ["selector_hint", "geo_selector", "selected_*_node_ids"],
    "replay_resolution_order": [
        "geo_select_nodes",
        "selection_query",
        "explicit_topo_refs",
        "stable_indices",
        "selector_hint",
    ],
}


def _canonical_contract_payload() -> Dict[str, Any]:
    return {
        "contract_version": CANONICAL_CONTRACT_VERSION,
        "graph_roles": {
            "graph": "canonical_low_level_graph",
            "leaf_ids": "explicit_result_set",
        },
        "replay_policy": {
            "preferred_graph": "graph",
            "default_mode": "strict",
            "permissive_mode": "explicit_opt_in",
        },
        "core_op_set": list(CANONICAL_CORE_OP_SET),
        "selection_ref_schema": {
            "edge_param": SELECTION_REF_SCHEMA["edge_param"],
            "face_param": SELECTION_REF_SCHEMA["face_param"],
            "edge_index_param": SELECTION_REF_SCHEMA["edge_index_param"],
            "face_index_param": SELECTION_REF_SCHEMA["face_index_param"],
            "required_topo_ref_fields": list(
                SELECTION_REF_SCHEMA["required_topo_ref_fields"]
            ),
            "optional_fields": list(SELECTION_REF_SCHEMA["optional_fields"]),
            "replay_resolution_order": list(
                SELECTION_REF_SCHEMA["replay_resolution_order"]
            ),
        },
    }


def _assert_graph_is_canonical(graph: OperationGraph) -> None:
    invalid_ops = sorted(
        {node.op for node in graph.nodes if node.op not in CANONICAL_CORE_OP_SET}
    )
    if invalid_ops:
        raise ValueError(
            "graph contains non-canonical operations: " + ", ".join(invalid_ops)
        )


def _as_vec3_tuple(value: Any) -> Tuple[float, float, float]:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("Expected a 3D vector-like value")
    return (float(value[0]), float(value[1]), float(value[2]))


# ---------------------------------------------------------------------------
# Export / Import
# ---------------------------------------------------------------------------


def export_graph_json(graph: OperationGraph, indent: int = 2) -> str:
    """Export an OperationGraph to a JSON string.

    Args:
        graph: The graph to export.
        indent: JSON indentation level.

    Returns:
        JSON string representation.
    """
    _assert_graph_is_canonical(graph)
    return graph.to_json(indent=indent)


def export_session_json(session: "GraphSession", indent: int = 2) -> str:
    """Export a graph session including its expression graph."""

    import json

    return json.dumps(
        {
            "graph": session.graph.to_dict(),
            "expression_graph": session.expression_graph.to_dict(),
            "frame_graph": session.frame_graph.to_dict(),
        },
        indent=indent,
    )


def import_graph_json(json_str: str) -> OperationGraph:
    """Import an OperationGraph from a JSON string.

    Args:
        json_str: JSON string to parse.

    Returns:
        Reconstructed OperationGraph.
    """
    import json

    try:
        payload = json.loads(json_str)
        schema_version = str(payload.get("schema_version", ""))
        if not schema_version.startswith("2."):
            raise ValueError(
                f"Unsupported graph schema_version '{schema_version}'. Expected 2.x."
            )
        graph = OperationGraph.from_dict(payload)
        _assert_graph_is_canonical(graph)
        return graph
    except Exception as e:
        raise_harness_error(
            operation="import_graph_json",
            what_happened="Failed to import the graph JSON payload.",
            possible_causes=[
                "The input string is not valid JSON.",
                "The payload does not follow the expected graph schema.",
                "The graph schema_version is unsupported.",
            ],
            how_to_fix=[
                "Pass a valid JSON string produced by export_graph_json().",
                "Make sure the payload includes a 2.x graph schema_version.",
                "If you edited the payload manually, validate the nodes and edges structure before retrying.",
            ],
            error=e,
        )


def import_session_json(json_str: str) -> Dict[str, Any]:
    """Import session payload containing graph and expression graph."""

    import json

    from .expr import ExpressionGraph
    from .frame import FrameGraph

    try:
        payload = json.loads(json_str)
        graph_payload = payload.get("graph")
        if not isinstance(graph_payload, dict):
            raise ValueError("Session payload is missing 'graph'")

        expr_payload = payload.get("expression_graph")
        if expr_payload is None:
            expr_graph = ExpressionGraph()
        elif isinstance(expr_payload, dict):
            expr_graph = ExpressionGraph.from_dict(expr_payload)
        else:
            raise ValueError("Session payload 'expression_graph' must be an object")

        frame_payload = payload.get("frame_graph")
        if frame_payload is None:
            frame_graph = FrameGraph()
        elif isinstance(frame_payload, dict):
            frame_graph = FrameGraph.from_dict(frame_payload)
        else:
            raise ValueError("Session payload 'frame_graph' must be an object")

        graph = OperationGraph.from_dict(graph_payload)
        _assert_graph_is_canonical(graph)

        return {
            "graph": graph,
            "expression_graph": expr_graph,
            "frame_graph": frame_graph,
        }
    except Exception as e:
        raise_harness_error(
            operation="import_session_json",
            what_happened="Failed to import the session JSON payload.",
            possible_causes=[
                "The input string is not valid JSON.",
                "The session payload is missing the required 'graph' object.",
                "The expression_graph or frame_graph fields use the wrong JSON type.",
            ],
            how_to_fix=[
                "Pass a valid JSON string produced by export_session_json().",
                "Make sure 'graph' is present and is a JSON object.",
                "Use JSON objects for 'expression_graph' and 'frame_graph', not strings or arrays.",
            ],
            error=e,
        )


def export_model_json(
    session: "GraphSession",
    indent: int = 2,
) -> str:
    """Export the canonical 2.0 model seed JSON.

    Current Phase 1 scope uses the active session as the container of:
    - operation graph
    - expression graph
    - capabilities/schema metadata
    """

    import json

    try:
        geometry_registry: List[Dict[str, Any]] = []
        semantic_entity_registry: List[Dict[str, Any]] = []
        sketch_profile_registry: List[Dict[str, Any]] = []
        semantic_delta_log: List[Dict[str, Any]] = []
        topology_delta_log: List[Dict[str, Any]] = []

        for node in session.graph.topological_order():
            if node.semantic_delta is not None:
                semantic_delta_log.append(
                    {
                        "node_id": node.node_id,
                        "op": node.op,
                        "delta": semantic_delta_to_dict(node.semantic_delta),
                    }
                )
                for ref in node.semantic_delta.created:
                    geometry_registry.append(
                        {
                            "graph_id": ref.graph_id,
                            "node_id": ref.node_id,
                            "entity_type": ref.entity_type,
                            "entity_id": ref.entity_id,
                            "source_op": node.op,
                        }
                    )
                    semantic_entity_registry.append(
                        {
                            "graph_id": ref.graph_id,
                            "node_id": ref.node_id,
                            "entity_type": ref.entity_type,
                            "entity_id": ref.entity_id,
                            "source_op": node.op,
                        }
                    )
            else:
                for slot in range(node.output_count):
                    geometry_registry.append(
                        {
                            "graph_id": session.graph.graph_id,
                            "node_id": node.node_id,
                            "entity_type": "ShapeOutput",
                            "entity_id": f"{node.op}:{slot}",
                            "source_op": node.op,
                        }
                    )

            if node.topo_delta is not None:
                topology_delta_log.append(
                    {
                        "node_id": node.node_id,
                        "op": node.op,
                        "delta": topo_delta_to_dict(node.topo_delta),
                    }
                )

            if node.op in {
                "make_point_rvertex",
                "make_line_redge",
                "make_circle_redge",
                "make_three_point_arc_redge",
                "make_angle_arc_redge",
                "make_spline_redge",
                "make_helix_redge",
                "make_wire_from_edges_rwire",
                "make_face_from_wire_rface",
            }:
                sketch_profile_registry.append(
                    {
                        "graph_id": session.graph.graph_id,
                        "node_id": node.node_id,
                        "op": node.op,
                        "params": dict(node.params),
                    }
                )

        frame_graph_payload = session.frame_graph.to_dict()

        _assert_graph_is_canonical(session.graph)
        leaf_ids = [node.node_id for node in session.graph.leaf_nodes()]

        payload: Dict[str, Any] = {
            "schema_version": MODEL_SCHEMA_VERSION,
            "canonical_contract": _canonical_contract_payload(),
            "graph": session.graph.to_dict(),
            "leaf_ids": leaf_ids,
            "expression_graph": session.expression_graph.to_dict(),
            "frame_graph": frame_graph_payload,
            "geometry_registry": geometry_registry,
            "semantic_entity_registry": semantic_entity_registry,
            "sketch_profile_registry": sketch_profile_registry,
            "semantic_delta_log": semantic_delta_log,
            "topology_delta_log": topology_delta_log,
        }

        return json.dumps(payload, indent=indent)
    except Exception as e:
        raise_harness_error(
            operation="export_model_json",
            what_happened="Failed to export the canonical model JSON payload.",
            possible_causes=[
                "The session contains non-serializable graph, expression, or frame data.",
                "The graph contains non-canonical operations instead of the strict low-level op set.",
            ],
            how_to_fix=[
                "Pass a valid GraphSession object built by SimpleCADAPI.",
                "Make sure composite builtins only emit strict low-level graph nodes before exporting model JSON.",
            ],
            error=e,
        )


def import_model_json(json_str: str) -> Dict[str, Any]:
    """Import canonical 2.0 model seed JSON."""

    import json

    try:
        payload = json.loads(json_str)
        schema_version = str(payload.get("schema_version", ""))
        if schema_version != MODEL_SCHEMA_VERSION:
            raise ValueError(
                f"Unsupported model schema_version '{schema_version}'; expected {MODEL_SCHEMA_VERSION}"
            )

        session_payload = import_session_json(
            json.dumps(
                {
                    "graph": payload.get("graph", {}),
                    "expression_graph": payload.get("expression_graph", {}),
                    "frame_graph": payload.get("frame_graph", {}),
                }
            )
        )
        graph = session_payload.get("graph")
        if isinstance(graph, OperationGraph):
            _assert_graph_is_canonical(graph)
        else:
            raise ValueError("Model payload does not contain a valid graph")
        session_payload["geometry_registry"] = list(
            payload.get("geometry_registry", [])
        )
        session_payload["canonical_contract"] = dict(
            payload.get("canonical_contract", _canonical_contract_payload())
        )
        session_payload["semantic_entity_registry"] = list(
            payload.get("semantic_entity_registry", [])
        )
        session_payload["sketch_profile_registry"] = list(
            payload.get("sketch_profile_registry", [])
        )
        session_payload["semantic_delta_log"] = list(
            payload.get("semantic_delta_log", [])
        )
        session_payload["topology_delta_log"] = list(
            payload.get("topology_delta_log", [])
        )
        session_payload["leaf_ids"] = [str(v) for v in payload.get("leaf_ids", [])]
        return session_payload
    except Exception as e:
        raise_harness_error(
            operation="import_model_json",
            what_happened="Failed to import the canonical model JSON payload.",
            possible_causes=[
                "The input string is not valid JSON.",
                f"The payload does not use the expected {MODEL_SCHEMA_VERSION} model schema_version.",
                "One or more nested graph payloads are malformed.",
            ],
            how_to_fix=[
                "Pass a valid JSON string produced by export_model_json().",
                f"Make sure schema_version is exactly {MODEL_SCHEMA_VERSION}.",
                "If you edited the payload manually, validate graph, expression_graph, and frame_graph fields before retrying.",
            ],
            error=e,
        )


def replay_model_json(json_str: str, *, strict: bool = True) -> List[AnyShape]:
    """Replay a model payload using its canonical low-level graph."""

    try:
        payload = import_model_json(json_str)
        graph = payload.get("graph")
        if not isinstance(graph, OperationGraph):
            raise ValueError("Model payload does not contain a replayable graph")

        explicit_leaf_ids = payload.get("leaf_ids")
        return _execute_graph(
            graph,
            cast(Optional[Sequence[str]], explicit_leaf_ids),
            strict=strict,
        )
    except Exception as e:
        raise_harness_error(
            operation="replay_model_json",
            what_happened="Failed to replay the model JSON payload.",
            possible_causes=[
                "The model payload is malformed or missing a replayable graph.",
                "The graph contains an unsupported or invalid node payload.",
                "One of the replayed operations failed due to invalid parameters or missing references.",
            ],
            how_to_fix=[
                "Start from export_model_json() output instead of hand-written payloads when possible.",
                "Make sure the model includes a valid canonical low-level graph section.",
                "If replay fails on a specific operation, inspect that node's params and compare them to the operation signature and help() output.",
            ],
            error=e,
        )


# ---------------------------------------------------------------------------
# Replay executor
# ---------------------------------------------------------------------------

# Registry mapping op names to factory functions.
# Each factory takes (params_dict) -> shape or list of shapes.
_OP_REGISTRY: Dict[str, Any] = {
    "make_cut_rsolidlist": lambda p: None,  # handled specially below
    "make_union_rsolid": lambda p: None,  # handled specially below
    "make_intersect_rsolidlist": lambda p: None,  # handled specially below
}


def _normalize_output(result: Any) -> List[AnyShape]:
    if result is None:
        return []
    if isinstance(result, list):
        return result
    return [result]


def _replay_primitive_or_simple(
    ctx: _ReplayContext,
    node,
    params: Dict[str, Any],
) -> Any:
    op_name = node.op
    node_id = node.node_id
    if op_name == "make_point_rvertex":
        ctx.require_params(node_id, op_name, params, ("x", "y", "z"))
        return ops.make_point_rvertex(params["x"], params["y"], params["z"])
    if op_name == "make_line_redge":
        ctx.require_params(node_id, op_name, params, ("start", "end"))
        return ops.make_line_redge(tuple(params["start"]), tuple(params["end"]))
    if op_name == "make_circle_redge":
        ctx.require_params(node_id, op_name, params, ("center", "radius", "normal"))
        return ops.make_circle_redge(
            tuple(params["center"]),
            params["radius"],
            tuple(params["normal"]),
        )
    if op_name == "make_three_point_arc_redge":
        ctx.require_params(node_id, op_name, params, ("start", "middle", "end"))
        return ops.make_three_point_arc_redge(
            tuple(params["start"]),
            tuple(params["middle"]),
            tuple(params["end"]),
        )
    if op_name == "make_angle_arc_redge":
        ctx.require_params(
            node_id,
            op_name,
            params,
            ("center", "radius", "start_angle", "end_angle", "normal"),
        )
        return ops.make_angle_arc_redge(
            tuple(params["center"]),
            params["radius"],
            params["start_angle"],
            params["end_angle"],
            tuple(params["normal"]),
        )
    if op_name == "make_spline_redge":
        ctx.require_params(node_id, op_name, params, ("points",))
        return ops.make_spline_redge(params["points"], tangents=params.get("tangents"))
    if op_name == "make_helix_redge":
        ctx.require_params(
            node_id, op_name, params, ("pitch", "height", "radius", "center", "dir")
        )
        return ops.make_helix_redge(
            params["pitch"],
            params["height"],
            params["radius"],
            center=tuple(params["center"]),
            dir=tuple(params["dir"]),
        )
    factory = _OP_REGISTRY.get(op_name)
    if factory:
        return factory(params)
    ctx.fail(f"No replay handler registered for graph node '{node_id}' ({op_name})")


def _shape_topo_ref_dict(shape: AnyShape) -> Dict[str, Any]:
    topo_ref = shape.get_metadata("topo_ref")
    return topo_ref if isinstance(topo_ref, dict) else {}


def _distance3(
    a: Optional[Tuple[float, float, float]], b: Optional[Tuple[float, float, float]]
) -> float:
    if a is None or b is None:
        return 1e6
    return math.dist(a, b)


def _tuple3_from_any(value: Any) -> Optional[Tuple[float, float, float]]:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    return None


def _shape_kind_token(shape: AnyShape) -> str:
    if isinstance(shape, Vertex):
        return "vertex"
    if isinstance(shape, Edge):
        return "edge"
    if isinstance(shape, Wire):
        return "wire"
    if isinstance(shape, Face):
        return "face"
    if isinstance(shape, Solid):
        return "solid"
    return type(shape).__name__.lower()


def _dedupe_shapes(shapes: Sequence[AnyShape]) -> List[AnyShape]:
    result: List[AnyShape] = []
    seen: set[str] = set()
    for shape in shapes:
        topo_id = getattr(shape, "topo_id", None)
        marker = f"{_shape_kind_token(shape)}:{topo_id}" if topo_id else str(id(shape))
        if marker in seen:
            continue
        seen.add(marker)
        result.append(shape)
    return result


def _candidate_shapes_for_geo_selection(source: AnyShape, kind: str) -> List[AnyShape]:
    kind = str(kind).lower()
    if kind == "solid":
        return [source] if isinstance(source, Solid) else []
    if kind == "face":
        if isinstance(source, Solid):
            return list(source.get_faces())
        return [source] if isinstance(source, Face) else []
    if kind == "edge":
        if hasattr(source, "get_edges"):
            return _dedupe_shapes(cast(Sequence[AnyShape], source.get_edges()))
        return [source] if isinstance(source, Edge) else []
    if kind == "wire":
        wires: List[AnyShape] = []
        if isinstance(source, Face):
            wires.append(source.get_outer_wire())
            wires.extend(source.get_inner_wires())
        elif isinstance(source, Solid):
            for face in source.get_faces():
                wires.append(face.get_outer_wire())
                wires.extend(face.get_inner_wires())
        elif hasattr(source, "get_children"):
            wires.extend(
                cast(AnyShape, child)
                for child in source.get_children()
                if isinstance(child, Wire)
            )
        elif isinstance(source, Wire):
            wires.append(source)
        return _dedupe_shapes(wires)
    if kind == "vertex":
        vertices: List[AnyShape] = []
        if isinstance(source, Edge):
            vertices.extend(cast(Sequence[AnyShape], source.get_children()))
        elif hasattr(source, "get_edges"):
            for edge in source.get_edges():
                vertices.extend(cast(Sequence[AnyShape], edge.get_children()))
        elif hasattr(source, "get_children"):
            vertices.extend(
                cast(AnyShape, child)
                for child in source.get_children()
                if isinstance(child, Vertex)
            )
        elif isinstance(source, Vertex):
            vertices.append(source)
        return _dedupe_shapes(vertices)
    return []


def _shape_geom_type(shape: AnyShape) -> Optional[str]:
    try:
        from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
        from OCP.GeomAbs import (
            GeomAbs_BSplineCurve,
            GeomAbs_BSplineSurface,
            GeomAbs_BezierCurve,
            GeomAbs_BezierSurface,
            GeomAbs_Circle,
            GeomAbs_Cone,
            GeomAbs_Cylinder,
            GeomAbs_Line,
            GeomAbs_Plane,
            GeomAbs_Sphere,
            GeomAbs_Torus,
        )

        if isinstance(shape, Edge):
            curve_type = BRepAdaptor_Curve(shape.wrapped).GetType()
            mapping = {
                GeomAbs_Line: "LINE",
                GeomAbs_Circle: "CIRCLE",
                GeomAbs_BSplineCurve: "BSPLINE",
                GeomAbs_BezierCurve: "BEZIER",
            }
            return mapping.get(
                curve_type,
                str(curve_type).replace("GeomAbs_CurveType.GeomAbs_", "").upper(),
            )
        if isinstance(shape, Face):
            surface_type = BRepAdaptor_Surface(shape.wrapped).GetType()
            mapping = {
                GeomAbs_Plane: "PLANE",
                GeomAbs_Cylinder: "CYLINDER",
                GeomAbs_Cone: "CONE",
                GeomAbs_Sphere: "SPHERE",
                GeomAbs_Torus: "TORUS",
                GeomAbs_BSplineSurface: "BSPLINE",
                GeomAbs_BezierSurface: "BEZIER",
            }
            return mapping.get(
                surface_type,
                str(surface_type)
                .replace("GeomAbs_SurfaceType.GeomAbs_", "")
                .upper(),
            )
    except Exception:
        return None
    return None


def _bbox_score(shape: AnyShape, selector: Dict[str, Any]) -> float:
    bbox = selector.get("bbox")
    if not isinstance(bbox, dict):
        return 0.0
    try:
        actual = bounding_box(shape.wrapped)
        expected_min = _tuple3_from_any(bbox.get("min"))
        expected_max = _tuple3_from_any(bbox.get("max"))
        if expected_min is None or expected_max is None:
            return 1e6
        return _distance3(
            (actual.xmin, actual.ymin, actual.zmin), expected_min
        ) + _distance3((actual.xmax, actual.ymax, actual.zmax), expected_max)
    except Exception:
        return 1e6


def _geo_selector_score(
    shape: AnyShape,
    selector: Dict[str, Any],
    *,
    candidate_index: Optional[int] = None,
) -> float:
    if _shape_kind_token(shape) != str(selector.get("kind", "")).lower():
        return 1e12

    score = _bbox_score(shape, selector) * 10.0

    expected_geom_type = selector.get("geom_type")
    if expected_geom_type is not None:
        actual_geom_type = _shape_geom_type(shape)
        if actual_geom_type is not None and actual_geom_type != str(expected_geom_type):
            score += 1e6

    if isinstance(shape, Vertex):
        score += _distance3(
            cast(Tuple[float, float, float], tuple(shape.get_coordinates())),
            _tuple3_from_any(selector.get("coordinates")),
        ) * 10.0
    elif isinstance(shape, Edge):
        if "length" in selector:
            score += abs(float(shape.get_length()) - float(selector["length"])) * 10.0
        center = shape.get_center()
        score += _distance3(
            (float(center.x), float(center.y), float(center.z)),
            _tuple3_from_any(selector.get("center")),
        ) * 10.0
        try:
            start = cast(
                Tuple[float, float, float],
                tuple(float(v) for v in shape.get_start_vertex().get_coordinates()),
            )
            end = cast(
                Tuple[float, float, float],
                tuple(float(v) for v in shape.get_end_vertex().get_coordinates()),
            )
            expected_start = _tuple3_from_any(selector.get("start"))
            expected_end = _tuple3_from_any(selector.get("end"))
            if expected_start is not None and expected_end is not None:
                direct = _distance3(start, expected_start) + _distance3(end, expected_end)
                reverse = _distance3(start, expected_end) + _distance3(end, expected_start)
                score += min(direct, reverse)
        except Exception:
            pass
    elif isinstance(shape, Wire):
        if "edge_count" in selector:
            score += abs(len(shape.get_edges()) - int(selector["edge_count"])) * 10.0
        if "closed" in selector and bool(shape.is_closed()) != bool(selector["closed"]):
            score += 10.0
    elif isinstance(shape, Face):
        if "area" in selector:
            score += abs(float(shape.get_area()) - float(selector["area"]))
        center = shape.get_center()
        score += _distance3(
            (float(center.x), float(center.y), float(center.z)),
            _tuple3_from_any(selector.get("center")),
        ) * 10.0
        normal = shape.get_normal_at()
        score += _distance3(
            (float(normal.x), float(normal.y), float(normal.z)),
            _tuple3_from_any(selector.get("normal")),
        ) * 5.0
        if "edge_count" in selector:
            score += abs(len(shape.get_edges()) - int(selector["edge_count"])) * 10.0
        if "inner_wire_count" in selector:
            score += abs(len(shape.get_inner_wires()) - int(selector["inner_wire_count"])) * 10.0
    elif isinstance(shape, Solid):
        if "volume" in selector:
            score += abs(float(shape.get_volume()) - float(selector["volume"]))

    return score


def _resolve_shape_from_geo_selector(source: AnyShape, selector: Dict[str, Any]) -> AnyShape:
    kind = str(selector.get("kind") or selector.get("target_kind") or "").lower()
    candidates = _candidate_shapes_for_geo_selection(source, kind)
    if not candidates:
        raise ValueError(f"geo selector found no {kind} candidates in source")

    ranked = sorted(
        enumerate(candidates),
        key=lambda item: _geo_selector_score(
            item[1], selector, candidate_index=int(item[0])
        ),
    )
    best_index, best_shape = ranked[0]
    best_score = _geo_selector_score(best_shape, selector, candidate_index=best_index)
    if best_score > 1e-4:
        raise ValueError(
            f"geo selector did not match a stable {kind} candidate; best score={best_score:.6g}"
        )
    return best_shape


def _edge_hint_score(edge: Edge, hint: Dict[str, Any]) -> float:
    score = 0.0
    if "length" in hint:
        score += abs(float(edge.get_length()) - float(hint["length"])) * 10.0

    start: Optional[Tuple[float, float, float]] = None
    end: Optional[Tuple[float, float, float]] = None
    try:
        start = cast(
            Tuple[float, float, float],
            tuple(float(v) for v in edge.get_start_vertex().get_coordinates()),
        )
        end = cast(
            Tuple[float, float, float],
            tuple(float(v) for v in edge.get_end_vertex().get_coordinates()),
        )
    except Exception:
        pass

    hint_start = hint.get("start")
    hint_end = hint.get("end")
    hint_start_tuple = _tuple3_from_any(hint_start)
    hint_end_tuple = _tuple3_from_any(hint_end)
    if (
        start is not None
        and end is not None
        and hint_start_tuple is not None
        and hint_end_tuple is not None
    ):
        direct = _distance3(start, hint_start_tuple) + _distance3(end, hint_end_tuple)
        reverse = _distance3(start, hint_end_tuple) + _distance3(end, hint_start_tuple)
        score += min(direct, reverse)
    elif hint.get("center") is not None:
        center = edge.get_center()
        center_tuple = (float(center.x), float(center.y), float(center.z))
        score += _distance3(center_tuple, _tuple3_from_any(hint["center"]))

    if "tags" in hint:
        hint_tags = set(hint["tags"])
        common = len(hint_tags & set(edge._list_tags()))
        score -= common * 0.1
    return score


def _face_hint_score(face: Face, hint: Dict[str, Any]) -> float:
    score = 0.0
    if "area" in hint:
        score += abs(float(face.get_area()) - float(hint["area"]))

    center = face.get_center()
    center_tuple = (float(center.x), float(center.y), float(center.z))
    hint_center = hint.get("center")
    hint_center_tuple = _tuple3_from_any(hint_center)
    if hint_center_tuple is not None:
        score += _distance3(center_tuple, hint_center_tuple) * 10.0

    hint_normal = hint.get("normal")
    hint_normal_tuple = _tuple3_from_any(hint_normal)
    if hint_normal_tuple is not None:
        normal = face.get_normal_at()
        normal_tuple = (float(normal.x), float(normal.y), float(normal.z))
        score += _distance3(normal_tuple, hint_normal_tuple) * 5.0

    if "tags" in hint:
        hint_tags = set(hint["tags"])
        common = len(hint_tags & set(face._list_tags()))
        score -= common * 0.1
    return score


def _resolve_edges_from_selector_hints(
    solid: Solid, refs: Sequence[Dict[str, Any]]
) -> List[Edge]:
    edges = solid.get_edges()
    remaining = list(edges)
    resolved: List[Edge] = []
    for ref_dict in refs:
        hint = ref_dict.get("selector_hint")
        if not isinstance(hint, dict) or not remaining:
            continue
        best = min(
            remaining,
            key=lambda edge: _edge_hint_score(edge, cast(Dict[str, Any], hint)),
        )
        resolved.append(best)
        remaining.remove(best)
    return resolved


def _resolve_faces_from_selector_hints(
    solid: Solid, refs: Sequence[Dict[str, Any]]
) -> List[Face]:
    faces = solid.get_faces()
    remaining = list(faces)
    resolved: List[Face] = []
    for ref_dict in refs:
        hint = ref_dict.get("selector_hint")
        if not isinstance(hint, dict) or not remaining:
            continue
        best = min(
            remaining,
            key=lambda face: _face_hint_score(face, cast(Dict[str, Any], hint)),
        )
        resolved.append(best)
        remaining.remove(best)
    return resolved


def _resolve_edges_from_refs(
    solid: Solid, refs: Sequence[Dict[str, Any]]
) -> List[Edge]:
    if not refs:
        return []
    edge_map = {
        _shape_topo_ref_dict(edge).get("topo_id"): edge
        for edge in solid.get_edges()
        if _shape_topo_ref_dict(edge)
    }
    resolved: List[Edge] = []
    for ref_dict in refs:
        ref = topo_ref_from_dict(ref_dict)
        edge = edge_map.get(ref.topo_id)
        if edge is not None:
            resolved.append(edge)
    return resolved


def _resolve_faces_from_refs(
    solid: Solid, refs: Sequence[Dict[str, Any]]
) -> List[Face]:
    if not refs:
        return []
    face_map = {
        _shape_topo_ref_dict(face).get("topo_id"): face
        for face in solid.get_faces()
        if _shape_topo_ref_dict(face)
    }
    resolved: List[Face] = []
    for ref_dict in refs:
        ref = topo_ref_from_dict(ref_dict)
        face = face_map.get(ref.topo_id)
        if face is not None:
            resolved.append(face)
    return resolved


def _resolve_edges_from_indices(solid: Solid, indices: Sequence[int]) -> List[Edge]:
    edges = solid.get_edges()
    return [edges[idx] for idx in indices if 0 <= idx < len(edges)]


def _resolve_faces_from_indices(solid: Solid, indices: Sequence[int]) -> List[Face]:
    faces = solid.get_faces()
    return [faces[idx] for idx in indices if 0 <= idx < len(faces)]


def _resolve_selector_scope(
    selector_payload: Dict[str, Any],
    default_scope: Solid,
    outputs: Dict[str, List[AnyShape]],
) -> Any:
    source_node_id = selector_payload.get("source_node_id")
    if source_node_id is None:
        return default_scope
    source_outputs = outputs.get(str(source_node_id), [])
    source_output_slot = int(selector_payload.get("source_output_slot", 0))
    if source_output_slot < 0 or source_output_slot >= len(source_outputs):
        raise ValueError(
            f"SelectionSpec source {source_node_id}:{source_output_slot} has no replay output"
        )
    return source_outputs[source_output_slot]


def _resolve_feature_selection(
    ctx: _ReplayContext,
    *,
    node,
    solid: Solid,
    params: Dict[str, Any],
    kind: str,
    outputs: Dict[str, List[AnyShape]],
) -> List[Any]:
    if kind == "edge":
        refs_param = "selected_edges"
        indices_param = "selected_edge_indices"
        node_ids_param = "selected_edge_node_ids"
        resolve_refs = _resolve_edges_from_refs
        resolve_indices = _resolve_edges_from_indices
        resolve_hints = _resolve_edges_from_selector_hints
    elif kind == "face":
        refs_param = "selected_faces"
        indices_param = "selected_face_indices"
        node_ids_param = "selected_face_node_ids"
        resolve_refs = _resolve_faces_from_refs
        resolve_indices = _resolve_faces_from_indices
        resolve_hints = _resolve_faces_from_selector_hints
    else:
        raise ValueError(f"unsupported selection kind: {kind}")

    selected_refs = cast(Sequence[Dict[str, Any]], params.get(refs_param, []))
    selection_node_ids = [str(node_id) for node_id in params.get(node_ids_param, [])]
    if selection_node_ids:
        resolved_from_nodes: List[AnyShape] = []
        for node_id in selection_node_ids:
            node_outputs = outputs.get(node_id, [])
            if not node_outputs:
                if ctx.strict:
                    ctx.fail(
                        f"Graph node '{node.node_id}' ({node.op}) selection node '{node_id}' has no replay output"
                    )
                continue
            resolved_from_nodes.extend(node_outputs)
        if resolved_from_nodes:
            return list(resolved_from_nodes)

    selection_query = params.get("selection_query")
    if isinstance(selection_query, dict):
        scope = _resolve_selector_scope(selection_query, solid, outputs)
        resolved = list(selector_from_dict(selection_query).resolve(scope))
        return resolved

    if selected_refs:
        resolved = resolve_refs(solid, selected_refs)
        if len(resolved) == len(selected_refs):
            return list(resolved)

    indices = cast(Sequence[int], params.get(indices_param, []))
    if indices:
        resolved = resolve_indices(solid, indices)
        if len(resolved) == len(indices):
            return list(resolved)

    if selected_refs:
        resolved = resolve_hints(solid, selected_refs)
        if len(resolved) == len(selected_refs):
            return list(resolved)

    return []


class _ReplayContext:
    def __init__(self, *, strict: bool) -> None:
        self.strict = bool(strict)

    def fail(self, message: str) -> None:
        raise ValueError(message)

    def require_params(
        self, node_id: str, op_name: str, params: Dict[str, Any], names: Sequence[str]
    ) -> None:
        missing = [name for name in names if name not in params]
        if missing:
            self.fail(
                f"Graph node '{node_id}' ({op_name}) is missing required parameter(s): "
                + ", ".join(missing)
            )


def _param(
    ctx: _ReplayContext,
    node_id: str,
    op_name: str,
    params: Dict[str, Any],
    name: str,
    default: Any = None,
) -> Any:
    if name in params:
        return params[name]
    if ctx.strict:
        ctx.fail(f"Graph node '{node_id}' ({op_name}) is missing required parameter '{name}'")
    return default


def _input_outputs(
    ctx: _ReplayContext,
    outputs: Dict[str, List[AnyShape]],
    node,
    index: int,
) -> List[AnyShape]:
    if len(node.inputs) <= index:
        if not ctx.strict:
            return []
        ctx.fail(
            f"Graph node '{node.node_id}' ({node.op}) is missing required input #{index}"
        )
    input_node = node.inputs[index]
    result = outputs.get(input_node.node_id)
    if not result:
        if not ctx.strict:
            return []
        ctx.fail(
            f"Graph node '{node.node_id}' ({node.op}) input '{input_node.node_id}' has no replay output"
        )
    return result


def _all_input_outputs(
    ctx: _ReplayContext,
    outputs: Dict[str, List[AnyShape]],
    node,
) -> List[AnyShape]:
    result: List[AnyShape] = []
    for input_node in node.inputs:
        input_outputs = outputs.get(input_node.node_id)
        if not input_outputs:
            if not ctx.strict:
                continue
            ctx.fail(
                f"Graph node '{node.node_id}' ({node.op}) input '{input_node.node_id}' has no replay output"
            )
        result.extend(input_outputs)
    return result


def _execute_graph(
    graph: OperationGraph,
    leaf_node_ids: Optional[Sequence[str]] = None,
    *,
    strict: bool = True,
) -> List[AnyShape]:
    ctx = _ReplayContext(strict=strict)
    if graph.node_count == 0:
        return []

    topo_order = graph.topological_order()

    # Store per-node outputs
    outputs: Dict[str, List[AnyShape]] = {}

    def _store_outputs(node, result: Any) -> None:
        result_list = _normalize_output(result)
        for idx, output in enumerate(result_list):
            attach_graph_node(
                output,
                node,
                output_slot=idx,
                graph_id=graph.graph_id,
            )
        outputs[node.node_id] = result_list

    with suspend_graph_recording():
        for node in topo_order:
            op_name = node.op
            params = node.params
            context_manager = (
                use_coordinate_system(node.context)
                if isinstance(node.context, dict)
                else nullcontext()
            )

            try:
                with context_manager:
                    if op_name in {
                        "make_select_rvertex",
                        "make_select_redge",
                        "make_select_rwire",
                        "make_select_rface",
                        "make_select_rsolid",
                    }:
                        ctx.require_params(
                            node.node_id, op_name, params, ("target_kind", "geo_selector")
                        )
                        source_outputs = _input_outputs(ctx, outputs, node, 0)
                        if source_outputs:
                            result = _resolve_shape_from_geo_selector(
                                source_outputs[0], cast(Dict[str, Any], params["geo_selector"])
                            )
                            _store_outputs(node, result)
                        continue

                    if op_name == "make_cut_rsolidlist":
                        ctx.require_params(
                            node.node_id, op_name, params, ("tool_count",)
                        )
                        if len(node.inputs) < 2:
                            if ctx.strict:
                                ctx.fail(
                                    f"Graph node '{node.node_id}' ({op_name}) requires at least two inputs"
                                )
                            continue
                        body_list = _input_outputs(ctx, outputs, node, 0)
                        tool_outputs: List[AnyShape] = []
                        for index in range(1, len(node.inputs)):
                            tool_outputs.extend(_input_outputs(ctx, outputs, node, index))
                        if not body_list or not tool_outputs:
                            continue
                        result = ops.cut_rsolidlist(
                            cast(Solid, body_list[0]),
                            [cast(Solid, tool) for tool in tool_outputs],
                            skip_non_intersecting=bool(
                                _param(
                                    ctx,
                                    node.node_id,
                                    op_name,
                                    params,
                                    "skip_non_intersecting",
                                    False,
                                )
                            ),
                        )
                        _store_outputs(node, result)
                        continue

                    if op_name == "make_union_rsolid":
                        if ctx.strict:
                            ctx.require_params(
                                node.node_id,
                                op_name,
                                params,
                                ("input_count", "clean", "glue", "tol"),
                            )
                        all_solids = [
                            cast(Solid, shape)
                            for shape in _all_input_outputs(ctx, outputs, node)
                        ]
                        if len(all_solids) >= 2:
                            result = ops.union_rsolid(
                                all_solids,
                                clean=bool(_param(ctx, node.node_id, op_name, params, "clean", True)),
                                glue=bool(_param(ctx, node.node_id, op_name, params, "glue", True)),
                                tol=cast(Optional[float], _param(ctx, node.node_id, op_name, params, "tol", None)),
                            )
                            _store_outputs(node, result)
                        elif all_solids and not ctx.strict:
                            _store_outputs(node, all_solids[0])
                        elif ctx.strict:
                            ctx.fail(
                                f"Graph node '{node.node_id}' ({op_name}) requires at least two solid inputs"
                            )
                        continue

                    if op_name == "make_intersect_rsolidlist":
                        ctx.require_params(
                            node.node_id, op_name, params, ("input_count",)
                        )
                        all_solids = [
                            cast(Solid, shape)
                            for shape in _all_input_outputs(ctx, outputs, node)
                        ]
                        if len(all_solids) >= 2:
                            result = ops.intersect_rsolidlist(
                                all_solids[0], all_solids[1:]
                            )
                            _store_outputs(node, result)
                        elif ctx.strict:
                            ctx.fail(
                                f"Graph node '{node.node_id}' ({op_name}) requires at least two solid inputs"
                            )
                        continue

                    if op_name == "make_face_from_wire_rface":
                        ctx.require_params(node.node_id, op_name, params, ("normal",))
                        wire_outputs = _input_outputs(ctx, outputs, node, 0)
                        if wire_outputs:
                            result = ops.make_face_from_wire_rface(
                                cast(Any, wire_outputs[0]),
                                normal=cast(Any, tuple(params["normal"])),
                            )
                            _store_outputs(node, result)
                        continue

                    if op_name == "make_wire_from_edges_rwire":
                        ctx.require_params(node.node_id, op_name, params, ("edge_count",))
                        edge_outputs = _all_input_outputs(ctx, outputs, node)
                        if edge_outputs:
                            result = ops.make_wire_from_edges_rwire(cast(Any, edge_outputs))
                            _store_outputs(node, result)
                        elif ctx.strict:
                            ctx.fail(
                                f"Graph node '{node.node_id}' ({op_name}) requires edge inputs"
                            )
                        continue

                    if op_name == "make_translate_rshape":
                        ctx.require_params(node.node_id, op_name, params, ("vector",))
                        input_outputs = _input_outputs(ctx, outputs, node, 0)
                        if input_outputs:
                            result = ops.translate_shape(
                                cast(AnyShape, input_outputs[0]),
                                cast(Any, tuple(params["vector"])),
                            )
                            _store_outputs(node, result)
                        continue

                    if op_name == "make_rotate_rshape":
                        ctx.require_params(
                            node.node_id, op_name, params, ("angle", "axis", "origin")
                        )
                        input_outputs = _input_outputs(ctx, outputs, node, 0)
                        if input_outputs:
                            result = ops.rotate_shape(
                                cast(AnyShape, input_outputs[0]),
                                params["angle"],
                                axis=cast(Any, tuple(params["axis"])),
                                origin=cast(Any, tuple(params["origin"])),
                            )
                            _store_outputs(node, result)
                        continue

                    if op_name == "make_extrude_rsolid":
                        ctx.require_params(
                            node.node_id, op_name, params, ("direction", "distance")
                        )
                        profile_outputs = _input_outputs(ctx, outputs, node, 0)
                        if profile_outputs:
                            result = ops.extrude_rsolid(
                                cast(Any, profile_outputs[0]),
                                cast(Any, tuple(params["direction"])),
                                params["distance"],
                            )
                            _store_outputs(node, result)
                        continue

                    if op_name == "make_revolve_rsolid":
                        ctx.require_params(
                            node.node_id,
                            op_name,
                            params,
                            ("axis", "angle", "origin"),
                        )
                        profile_outputs = _input_outputs(ctx, outputs, node, 0)
                        if profile_outputs:
                            result = ops.revolve_rsolid(
                                cast(Any, profile_outputs[0]),
                                axis=cast(Any, tuple(params["axis"])),
                                angle=params["angle"],
                                origin=cast(Any, tuple(params["origin"])),
                            )
                            _store_outputs(node, result)
                        continue

                    if op_name == "make_loft_rsolid":
                        ctx.require_params(
                            node.node_id, op_name, params, ("profile_count", "ruled")
                        )
                        profile_outputs = _all_input_outputs(ctx, outputs, node)
                        if profile_outputs:
                            result = ops.loft_rsolid(
                                cast(Any, profile_outputs), ruled=bool(params["ruled"])
                            )
                            _store_outputs(node, result)
                        elif ctx.strict:
                            ctx.fail(
                                f"Graph node '{node.node_id}' ({op_name}) requires profile inputs"
                            )
                        continue

                    if op_name == "make_sweep_rsolid":
                        ctx.require_params(node.node_id, op_name, params, ("is_frenet",))
                        profile_outputs = _input_outputs(ctx, outputs, node, 0)
                        path_outputs = _input_outputs(ctx, outputs, node, 1)
                        if profile_outputs and path_outputs:
                            result = ops.sweep_rsolid(
                                cast(Any, profile_outputs[0]),
                                cast(Any, path_outputs[0]),
                                is_frenet=bool(params["is_frenet"]),
                            )
                            _store_outputs(node, result)
                        continue

                    if op_name == "make_mirror_rshape":
                        ctx.require_params(
                            node.node_id,
                            op_name,
                            params,
                            ("plane_origin", "plane_normal"),
                        )
                        input_outputs = _input_outputs(ctx, outputs, node, 0)
                        if input_outputs:
                            result = ops.mirror_shape(
                                cast(Any, input_outputs[0]),
                                cast(Any, tuple(params["plane_origin"])),
                                cast(Any, tuple(params["plane_normal"])),
                            )
                            _store_outputs(node, result)
                        continue

                    if op_name == "make_fillet_rsolid":
                        ctx.require_params(
                            node.node_id,
                            op_name,
                            params,
                            ("radius", "edge_count"),
                        )
                        input_outputs = _input_outputs(ctx, outputs, node, 0)
                        if input_outputs:
                            solid = cast(Solid, input_outputs[0])
                            edges = cast(
                                List[Edge],
                                _resolve_feature_selection(
                                    ctx,
                                    node=node,
                                    solid=solid,
                                    params=params,
                                    kind="edge",
                                    outputs=outputs,
                                ),
                            )
                            expected = int(params["edge_count"])
                            if ctx.strict and len(edges) != expected:
                                ctx.fail(
                                    f"Graph node '{node.node_id}' ({op_name}) expected {expected} selected edge(s), got {len(edges)}"
                                )
                            result = ops.fillet_rsolid(solid, edges, params["radius"])
                            _store_outputs(node, result)
                        continue

                    if op_name == "make_chamfer_rsolid":
                        ctx.require_params(
                            node.node_id,
                            op_name,
                            params,
                            ("distance", "edge_count"),
                        )
                        input_outputs = _input_outputs(ctx, outputs, node, 0)
                        if input_outputs:
                            solid = cast(Solid, input_outputs[0])
                            edges = cast(
                                List[Edge],
                                _resolve_feature_selection(
                                    ctx,
                                    node=node,
                                    solid=solid,
                                    params=params,
                                    kind="edge",
                                    outputs=outputs,
                                ),
                            )
                            expected = int(params["edge_count"])
                            if ctx.strict and len(edges) != expected:
                                ctx.fail(
                                    f"Graph node '{node.node_id}' ({op_name}) expected {expected} selected edge(s), got {len(edges)}"
                                )
                            result = ops.chamfer_rsolid(solid, edges, params["distance"])
                            _store_outputs(node, result)
                        continue

                    if op_name == "make_shell_rsolid":
                        ctx.require_params(
                            node.node_id,
                            op_name,
                            params,
                            ("thickness", "removed_face_count"),
                        )
                        input_outputs = _input_outputs(ctx, outputs, node, 0)
                        if input_outputs:
                            solid = cast(Solid, input_outputs[0])
                            faces = cast(
                                List[Face],
                                _resolve_feature_selection(
                                    ctx,
                                    node=node,
                                    solid=solid,
                                    params=params,
                                    kind="face",
                                    outputs=outputs,
                                ),
                            )
                            expected = int(params["removed_face_count"])
                            if ctx.strict and len(faces) != expected:
                                ctx.fail(
                                    f"Graph node '{node.node_id}' ({op_name}) expected {expected} selected face(s), got {len(faces)}"
                                )
                            result = ops.shell_rsolid(solid, faces, params["thickness"])
                            _store_outputs(node, result)
                        continue

                    result = _replay_primitive_or_simple(ctx, node, params)
                    _store_outputs(node, result)
            except Exception as exc:
                raise ValueError(
                    f"Failed to replay graph node '{node.node_id}' ({op_name}): {exc}"
                ) from exc

    leaf_results: List[AnyShape] = []
    if leaf_node_ids is None:
        target_leaf_ids = [leaf.node_id for leaf in graph.leaf_nodes()]
    else:
        target_leaf_ids = [str(node_id) for node_id in leaf_node_ids]
    for node_id in target_leaf_ids:
        if node_id not in outputs:
            if ctx.strict:
                ctx.fail(f"Leaf node '{node_id}' has no replay output")
            continue
        leaf_results.extend(outputs[node_id])

    return leaf_results


def replay_graph(graph: OperationGraph, *, strict: bool = True) -> List[AnyShape]:
    """Replay an OperationGraph to rebuild the model.

    Executes nodes in topological order. Primitives are created from their
    parameters; boolean operations consume upstream outputs.

    Args:
        graph: The graph to replay.

    Returns:
        List of leaf-node outputs. These may be solids, faces, wires, edges,
        or vertices depending on the workflow.
    """

    return _execute_graph(graph, strict=strict)
