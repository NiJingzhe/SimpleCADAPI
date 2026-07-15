"""SimpleCAD API operation implementations based on the README design."""

from __future__ import annotations

import re
import uuid
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union, cast
import math
import numpy as np

from ._vendor_warning_filters import suppress_vendor_deprecation_warnings
from .errors import SimpleCADError, raise_harness_error

suppress_vendor_deprecation_warnings()

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex
from OCP.gp import gp_Pnt

from .core import (
    Vertex,
    Edge,
    Wire,
    Face,
    Solid,
    Compound,
    AnyShape,
    clone_semantic_shape_view,
    get_current_cs,
)
from .autotag import apply_tracking_tags_to_delta
from .expr import ScalarLike, evaluate_scalar, evaluate_value
from .graph import (
    attach_graph_node,
    attach_semantic_graph_node,
    get_active_session,
    record_operation,
    record_operation_if_active,
    suspend_graph_recording,
)
from .ql import ShapeSelector, output_role
from .product import (
    Assembly,
    Component,
    Connector,
    ConnectorAnchor,
    ConnectorRef,
    Constraint,
    ConstraintReport,
    ConstraintResidual,
    GeometryRef,
    Material,
    Part,
    Placement,
    ScalarLimit,
    compose_placements,
    coupling_phase_offset,
    identity_placement,
    inspect_assembly_constraints,
    measure_constraint_residual,
    solve_assembly_constraints,
)
from .sketch import Sketch, SketchRef, SketchSolveResult
from .tagging import (
    LineagePolicy,
    SemanticCapabilityError,
    TagBinding,
    TagBindingScope,
    TagCertainty,
    TagEvidence,
    TagLifecycle,
    TagProducer,
    TagPropagation,
    TagScope,
    TagTarget,
    TopologyPropagation,
    lineage_policy_allows,
    normalize_tag,
    normalize_tag_scope,
)
from .topology import (
    SemanticDelta,
    SemanticRef,
    TopoDelta,
    TopoEntry,
    TopoRef,
    topo_ref_to_dict,
)
from .tracking import (
    TrackedBooleanResult,
    TrackedResult,
    tracked_chamfer,
    tracked_cut,
    tracked_extrude,
    tracked_fillet,
    tracked_intersect,
    tracked_mirror,
    tracked_loft,
    tracked_revolve,
    tracked_rotate,
    tracked_shell,
    tracked_sweep,
    tracked_translate,
    tracked_union,
)
from .kernel.ocp_builders import (
    make_box_solid,
    make_cone_solid,
    make_cylinder_solid,
    make_sphere_solid,
)
from .kernel.ocp_curves import (
    make_arc_angle_edge,
    make_arc_three_point_edge,
    make_bspline_edge,
    make_circle_edge,
    make_helix_wire,
    make_line_edge,
    make_polyline_wire,
    make_wire_from_edges as make_wire_from_edges_ocp,
)
from .kernel.ocp_features import (
    make_face_from_wire as make_face_from_wire_ocp,
    make_face_from_wires as make_face_from_wires_ocp,
    make_helical_sweep_solid,
    make_loft_solid,
    make_sweep_solid,
)
from .kernel.ocp_transforms import (
    mirror_shape_ocp,
    rotate_shape_ocp,
    place_shape_ocp,
    translate_shape_ocp,
)
from .kernel.ocp_booleans import common_shapes, cut_shapes, fuse_shapes, solids_of
from .kernel.ocp_topology import faces_of as faces_of_ocp
from .kernel.ocp_export import (
    export_step_shapes,
    export_stl_shape,
    make_compound,
    make_compound_always,
)
from .kernel.ocp_mesh import tessellate_face
from .kernel.ocp_properties import bounding_box, distance as ocp_distance


_DEFAULT_UNION_GLUE = True
_DEFAULT_UNION_TOL_FACTOR = 1e-7
_DEFAULT_UNION_TOL_MIN = 1e-7
_DEFAULT_UNION_TOL_MAX = 1e-5


_OP_MAKE_POINT_RVERTEX = "make_point_rvertex"
_OP_MAKE_LINE_REDGE = "make_line_redge"
_OP_MAKE_CIRCLE_REDGE = "make_circle_redge"
_OP_MAKE_THREE_POINT_ARC_REDGE = "make_three_point_arc_redge"
_OP_MAKE_ANGLE_ARC_REDGE = "make_angle_arc_redge"
_OP_MAKE_SPLINE_REDGE = "make_spline_redge"
_OP_MAKE_HELIX_REDGE = "make_helix_redge"
_OP_MAKE_WIRE_FROM_EDGES_RWIRE = "make_wire_from_edges_rwire"
_OP_MAKE_FACE_FROM_WIRE_RFACE = "make_face_from_wire_rface"
_OP_MAKE_FACE_FROM_WIRES_RFACE = "make_face_from_wires_rface"
_OP_MAKE_TRANSLATE_RSHAPE = "make_translate_rshape"
_OP_MAKE_ROTATE_RSHAPE = "make_rotate_rshape"
_OP_MAKE_MIRROR_RSHAPE = "make_mirror_rshape"
_OP_MAKE_EXTRUDE_RSOLID = "make_extrude_rsolid"
_OP_MAKE_REVOLVE_RSOLID = "make_revolve_rsolid"
_OP_MAKE_LOFT_RSOLID = "make_loft_rsolid"
_OP_MAKE_SWEEP_RSOLID = "make_sweep_rsolid"
_OP_MAKE_UNION_RSOLID = "make_union_rsolid"
_OP_MAKE_CUT_RSOLID = "make_cut_rsolid"
_OP_MAKE_INTERSECT_RSOLID = "make_intersect_rsolid"
_OP_MAKE_CUT_RFACE = "make_2d_cut_rface"
_OP_MAKE_UNION_RFACE = "make_2d_union_rface"
_OP_MAKE_INTERSECT_RFACE = "make_2d_intersect_rface"
_OP_MAKE_FILLET_RSOLID = "make_fillet_rsolid"
_OP_MAKE_CHAMFER_RSOLID = "make_chamfer_rsolid"
_OP_MAKE_SHELL_RSOLID = "make_shell_rsolid"
_OP_MAKE_SELECT_RVERTEX = "make_select_rvertex"
_OP_MAKE_SELECT_REDGE = "make_select_redge"
_OP_MAKE_SELECT_RWIRE = "make_select_rwire"
_OP_MAKE_SELECT_RFACE = "make_select_rface"
_OP_MAKE_SELECT_RSOLID = "make_select_rsolid"
_OP_APPLY_TAG_RSELECTION = "apply_tag_rselection"
_OP_MAKE_SKETCH_RSKETCH = "make_sketch_rsketch"
_OP_MAKE_ADD_POINT_RSKETCH = "make_add_point_rsketch"
_OP_MAKE_ADD_LINE_RSKETCH = "make_add_line_rsketch"
_OP_MAKE_ADD_CIRCLE_RSKETCH = "make_add_circle_rsketch"
_OP_MAKE_WIRE_FROM_SKETCH_RWIRE = "make_wire_from_sketch_rwire"
_OP_MAKE_FACE_FROM_SKETCH_RFACE = "make_face_from_sketch_rface"
_OP_MAKE_MATERIAL_RMATERIAL = "make_material_rmaterial"
_OP_MAKE_PLACEMENT_RPLACEMENT = "make_placement_rplacement"
_OP_MAKE_IDENTITY_PLACEMENT_RPLACEMENT = "make_identity_placement_rplacement"
_OP_MAKE_PART_RPART = "make_part_rpart"
_OP_MAKE_ASSIGN_MATERIAL_RPART = "make_assign_material_rpart"
_OP_MAKE_ASSEMBLY_RASSEMBLY = "make_assembly_rassembly"
_OP_MAKE_ADD_COMPONENT_RASSEMBLY = "make_add_component_rassembly"
_OP_MAKE_PLACE_COMPONENT_RASSEMBLY = "make_place_component_rassembly"
_OP_MAKE_COMPOUND_FROM_ASSEMBLY_RCOMPOUND = "make_compound_from_assembly_rcompound"
_OP_MAKE_FACE_CONNECTOR_RCONNECTOR = "make_face_connector_rconnector"
_OP_MAKE_EDGE_CONNECTOR_RCONNECTOR = "make_edge_connector_rconnector"
_OP_MAKE_VERTEX_CONNECTOR_RCONNECTOR = "make_vertex_connector_rconnector"
_OP_MAKE_PLACEMENT_CONNECTOR_RCONNECTOR = "make_placement_connector_rconnector"
_OP_MAKE_ADD_CONNECTOR_RPART = "make_add_connector_rpart"
_OP_MAKE_ADD_CONNECTOR_RASSEMBLY = "make_add_connector_rassembly"
_OP_MAKE_FORWARD_CONNECTOR_RASSEMBLY = "make_forward_connector_rassembly"
_OP_MAKE_CONNECTOR_REF_RCONNECTORREF = "make_connector_ref_rconnectorref"
_OP_MAKE_SCALAR_LIMIT_RSCALARLIMIT = "make_scalar_limit_rscalarlimit"
_OP_MAKE_GROUND_COMPONENT_RASSEMBLY = "make_ground_component_rassembly"
_OP_MAKE_UNGROUND_COMPONENT_RASSEMBLY = "make_unground_component_rassembly"
_OP_MAKE_FIXED_CONSTRAINT_RASSEMBLY = "make_fixed_constraint_rassembly"
_OP_MAKE_REVOLUTE_CONSTRAINT_RASSEMBLY = "make_revolute_constraint_rassembly"
_OP_MAKE_PRISMATIC_CONSTRAINT_RASSEMBLY = "make_prismatic_constraint_rassembly"
_OP_MAKE_GEAR_CONSTRAINT_RASSEMBLY = "make_gear_constraint_rassembly"
_OP_MAKE_BELT_CONSTRAINT_RASSEMBLY = "make_belt_constraint_rassembly"
_OP_MAKE_RACK_PINION_CONSTRAINT_RASSEMBLY = "make_rack_pinion_constraint_rassembly"
_OP_MAKE_SOLVE_ASSEMBLY_CONSTRAINTS_RASSEMBLY = (
    "make_solve_assembly_constraints_rassembly"
)


_OPERATION_OUTPUT_ROLE_CARDINALITY: Dict[str, Tuple[Tuple[str, str], ...]] = {
    _OP_MAKE_EXTRUDE_RSOLID: (
        ("extrusion.start", "one"),
        ("extrusion.end", "one"),
        ("extrusion.side", "many"),
    ),
    _OP_MAKE_REVOLVE_RSOLID: (
        ("revolution.start", "one"),
        ("revolution.end", "one"),
        ("revolution.side", "many"),
    ),
    _OP_MAKE_FILLET_RSOLID: (("fillet.patch", "many"),),
    _OP_MAKE_CHAMFER_RSOLID: (("chamfer.patch", "many"),),
    _OP_MAKE_SHELL_RSOLID: (
        ("shell.body_face", "many"),
        ("shell.offset_face", "many"),
        ("shell.closing_descendant", "many"),
        ("shell.wall", "many"),
    ),
    _OP_MAKE_LOFT_RSOLID: (
        ("loft.start", "one"),
        ("loft.end", "one"),
        ("loft.side", "many"),
    ),
    _OP_MAKE_SWEEP_RSOLID: (
        ("sweep.start", "one"),
        ("sweep.end", "one"),
        ("sweep.side", "many"),
    ),
}


_SKETCH_CONSTRAINT_OPS = {
    "coincident": "make_constrain_coincident_rsketch",
    "connect": "make_constrain_coincident_rsketch",
    "point_on": "make_constrain_point_on_rsketch",
    "horizontal": "make_constrain_horizontal_rsketch",
    "vertical": "make_constrain_vertical_rsketch",
    "parallel": "make_constrain_parallel_rsketch",
    "perpendicular": "make_constrain_perpendicular_rsketch",
    "collinear": "make_constrain_collinear_rsketch",
    "tangent": "make_constrain_tangent_rsketch",
    "concentric": "make_constrain_concentric_rsketch",
    "midpoint": "make_constrain_midpoint_rsketch",
    "symmetric": "make_constrain_symmetric_rsketch",
    "equal_length": "make_constrain_equal_length_rsketch",
    "equal_radius": "make_constrain_equal_radius_rsketch",
    "distance": "make_constrain_distance_rsketch",
    "distance_x": "make_constrain_distance_x_rsketch",
    "distance_y": "make_constrain_distance_y_rsketch",
    "length": "make_constrain_length_rsketch",
    "angle": "make_constrain_angle_rsketch",
    "radius": "make_constrain_radius_rsketch",
    "diameter": "make_constrain_diameter_rsketch",
    "fix": "make_constrain_fix_rsketch",
}


def _orthonormal_plane_axes(
    normal: Tuple[float, float, float],
) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    normal_vec = np.array(normal, dtype=float)
    norm = float(np.linalg.norm(normal_vec))
    if norm <= 1e-12:
        raise ValueError("法向量不能是零向量")
    z_axis = normal_vec / norm
    ref_vec = (
        np.array([1.0, 0.0, 0.0]) if abs(z_axis[2]) > 0.9 else np.array([0.0, 0.0, 1.0])
    )
    x_axis = np.cross(z_axis, ref_vec)
    x_norm = float(np.linalg.norm(x_axis))
    if x_norm <= 1e-12:
        raise ValueError("无法根据给定法向量构建局部坐标系")
    x_axis = x_axis / x_norm
    y_axis = np.cross(z_axis, x_axis)
    y_axis = y_axis / float(np.linalg.norm(y_axis))
    return z_axis, x_axis, y_axis


def _pick_perpendicular_unit(axis: Tuple[float, float, float]) -> np.ndarray:
    axis_vec = np.array(axis, dtype=float)
    axis_norm = float(np.linalg.norm(axis_vec))
    if axis_norm <= 1e-12:
        raise ValueError("轴向量不能是零向量")
    axis_unit = axis_vec / axis_norm
    ref_vec = (
        np.array([1.0, 0.0, 0.0])
        if abs(axis_unit[2]) > 0.9
        else np.array([0.0, 0.0, 1.0])
    )
    radial = np.cross(axis_unit, ref_vec)
    radial_norm = float(np.linalg.norm(radial))
    if radial_norm <= 1e-12:
        raise ValueError("无法根据给定轴向量构建旋转剖面")
    return radial / radial_norm


def _offset_point_expr(
    center: Tuple[ScalarLike, ScalarLike, ScalarLike],
    x_axis: Sequence[float],
    y_axis: Sequence[float],
    dx: ScalarLike,
    dy: ScalarLike,
) -> Tuple[ScalarLike, ScalarLike, ScalarLike]:
    return (
        center[0] + dx * float(x_axis[0]) + dy * float(y_axis[0]),
        center[1] + dx * float(x_axis[1]) + dy * float(y_axis[1]),
        center[2] + dx * float(x_axis[2]) + dy * float(y_axis[2]),
    )


def _make_closed_profile_rwire(
    points: Sequence[Tuple[ScalarLike, ScalarLike, ScalarLike]],
) -> Wire:
    edges = [
        make_line_redge(points[idx], points[(idx + 1) % len(points)])
        for idx in range(len(points))
    ]
    return make_wire_from_edges_rwire(edges)


def _make_closed_profile_rface(
    points: Sequence[Tuple[ScalarLike, ScalarLike, ScalarLike]],
    *,
    normal: Tuple[float, float, float] = (0.0, 0.0, 1.0),
) -> Face:
    wire = _make_closed_profile_rwire(points)
    return make_face_from_wire_rface(wire, normal=normal)


def _wrap_public_api_error(
    *,
    operation: str,
    what_happened: str,
    possible_causes: Sequence[str],
    how_to_fix: Sequence[str],
    error: BaseException,
) -> None:
    raise_harness_error(
        operation=operation,
        what_happened=what_happened,
        possible_causes=possible_causes,
        how_to_fix=how_to_fix,
        error=error,
    )


def _semantic_id_registry(kind: str) -> Set[str]:
    session = get_active_session()
    if session is None:
        return set()
    registry = getattr(session, "_simplecad_semantic_ids", None)
    if registry is None:
        registry = {}
        setattr(session, "_simplecad_semantic_ids", registry)
    return cast(Set[str], registry.setdefault(kind, set()))


def _reserve_semantic_id(kind: str, value: str) -> None:
    session = get_active_session()
    if session is None:
        return
    registry = _semantic_id_registry(kind)
    if value in registry:
        raise ValueError(f"duplicate {kind} id in active GraphSession: {value}")
    registry.add(value)


def _semantic_created(
    entity_type: str, entity_id: str, metadata: Optional[Dict[str, Any]] = None
) -> SemanticDelta:
    return SemanticDelta(
        created=(
            SemanticRef(
                graph_id="pending",
                node_id="pending",
                entity_type=entity_type,
                entity_id=entity_id,
            ),
        ),
        metadata=dict(metadata or {}),
    )


def _semantic_modified(
    entity_type: str, entity_id: str, metadata: Optional[Dict[str, Any]] = None
) -> SemanticDelta:
    return SemanticDelta(
        modified=(
            SemanticRef(
                graph_id="pending",
                node_id="pending",
                entity_type=entity_type,
                entity_id=entity_id,
            ),
        ),
        metadata=dict(metadata or {}),
    )


def _material_params(material: Material) -> Dict[str, object]:
    return material.to_dict()


def _placement_params(placement: Placement) -> Dict[str, object]:
    return {
        "origin": placement.origin,
        "x_axis": placement.x_axis,
        "y_axis": placement.y_axis,
    }


def _part_params(part: Part) -> Dict[str, object]:
    return {"part_id": part.part_id, "name": part.name}


def _assembly_params(assembly: Assembly) -> Dict[str, object]:
    return {"assembly_id": assembly.assembly_id, "name": assembly.name}


def _connector_params(connector: Connector) -> Dict[str, object]:
    return connector.to_dict()


def _connector_ref_params(connector_ref: ConnectorRef) -> Dict[str, object]:
    return connector_ref.to_dict()


def _scalar_limit_params(limit: ScalarLimit) -> Dict[str, object]:
    return limit.to_dict()


def _constraint_params(constraint: Constraint) -> Dict[str, object]:
    return constraint.to_dict()


def _resolve_union_tol(
    solids: Sequence[Solid], tol: Optional[float]
) -> Optional[float]:
    """Resolve a conservative fuzzy tolerance for boolean union.

    When callers do not specify `tol`, use a scale-aware value that is large enough
    to absorb small numerical noise but not aggressive enough to close meaningful
    modeling gaps by default.
    """

    if tol is not None:
        return tol

    bbox_min = np.array([np.inf, np.inf, np.inf], dtype=float)
    bbox_max = np.array([-np.inf, -np.inf, -np.inf], dtype=float)

    for solid in solids:
        bb = bounding_box(solid.wrapped)
        bbox_min = np.minimum(bbox_min, np.array([bb.xmin, bb.ymin, bb.zmin]))
        bbox_max = np.maximum(bbox_max, np.array([bb.xmax, bb.ymax, bb.zmax]))

    span = float(np.linalg.norm(bbox_max - bbox_min))
    if not np.isfinite(span) or span <= 0:
        return _DEFAULT_UNION_TOL_MIN

    return min(
        max(span * _DEFAULT_UNION_TOL_FACTOR, _DEFAULT_UNION_TOL_MIN),
        _DEFAULT_UNION_TOL_MAX,
    )


def _union_separation_diagnostic(
    results: Sequence[Solid], tol: Optional[float]
) -> Optional[str]:
    """Return a short diagnostic for multi-solid union results."""

    if len(results) < 2:
        return None

    effective_tol = float(tol or 0.0)
    nearest_gap_above_tol: Optional[float] = None

    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            gap = float(ocp_distance(results[i].wrapped, results[j].wrapped))
            if gap > effective_tol:
                if nearest_gap_above_tol is None or gap < nearest_gap_above_tol:
                    nearest_gap_above_tol = gap

    if nearest_gap_above_tol is None:
        return None

    return (
        f"union produced {len(results)} separated solids; "
        f"nearest detected gap is about {nearest_gap_above_tol:.6g}, "
        f"which exceeds tol={effective_tol:.6g}"
    )


def _flatten_boolean_solids(
    args: Sequence[Union[Solid, Sequence[Solid]]], operation_name: str
) -> List[Solid]:
    """Flatten nested boolean inputs into a validated solid list."""

    def _flatten(values: Sequence[Union[Solid, Sequence[Solid]]]) -> List[Solid]:
        flattened: List[Solid] = []
        for value in values:
            if isinstance(value, Solid):
                flattened.append(value)
            elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
                flattened.extend(
                    _flatten(cast(Sequence[Union[Solid, Sequence[Solid]]], value))
                )
            else:
                raise ValueError(f"{operation_name}函数只接受Solid类型的对象")
        return flattened

    return _flatten(args)


def _require_single_boolean_solid(
    result_shapes: Sequence[Any],
    *,
    operation: str,
    failure_reason: str,
) -> Solid:
    if not result_shapes:
        raise ValueError(failure_reason)
    if len(result_shapes) != 1:
        raise ValueError(
            f"{operation} 期望得到单个Solid结果，但内核返回了 {len(result_shapes)} 个实体。"
        )
    return Solid(result_shapes[0])


def _merge_topo_deltas(deltas: Sequence[TopoDelta]) -> Optional[TopoDelta]:
    if not deltas:
        return None
    preserved: List[TopoRef] = []
    modified: List[TopoRef] = []
    generated: List[TopoRef] = []
    deleted: List[TopoRef] = []
    section_edges: List[TopoRef] = []
    entries: List[TopoEntry] = []
    raw_event: Dict[str, Any] = {"steps": []}

    for idx, delta in enumerate(deltas):
        preserved.extend(delta.preserved)
        modified.extend(delta.modified)
        generated.extend(delta.generated)
        deleted.extend(delta.deleted)
        section_edges.extend(delta.section_edges)
        entries.extend(delta.entries)
        raw_event["steps"].append(
            {
                "index": idx,
                "preserved": len(delta.preserved),
                "modified": len(delta.modified),
                "generated": len(delta.generated),
                "deleted": len(delta.deleted),
                "section_edges": len(delta.section_edges),
            }
        )

    return TopoDelta(
        preserved=tuple(preserved),
        modified=tuple(modified),
        generated=tuple(generated),
        deleted=tuple(deleted),
        section_edges=tuple(section_edges),
        entries=tuple(entries),
        raw_event=raw_event,
    )


def _copy_runtime_state(source: AnyShape, target: AnyShape) -> AnyShape:
    runtime = getattr(source, "_runtime", None)
    if isinstance(runtime, dict):
        target._runtime = runtime.copy()
    return target


def _attach_lineage_from_source(
    source: AnyShape,
    target: AnyShape,
    *,
    derivation: str,
    op: str,
    coverage: str = "complete",
) -> None:
    evidence = TagEvidence(
        "topology_change",
        {
            "op": op,
            "derivation": derivation,
            "coverage": coverage,
        },
    )
    bindings = list(source._local_tag_bindings())
    bindings.extend(
        witness.binding
        for witness in source._tag_lineage
        if witness.coverage == "complete"
        and lineage_policy_allows(witness.binding.propagation, witness.derivation)
    )
    unique_bindings = {binding.binding_id: binding for binding in bindings}
    for binding in unique_bindings.values():
        target._add_tag_lineage(
            binding,
            derivation=derivation,
            source_topo_id=source.topo_id,
            evidence=evidence,
            coverage=coverage,
        )
    target._set_runtime("semantic.lineage.coverage", coverage)


def _current_context_metadata() -> Dict[str, Tuple[float, float, float]]:
    cs = get_current_cs()
    return {
        "origin": (float(cs.origin[0]), float(cs.origin[1]), float(cs.origin[2])),
        "x_axis": (float(cs.x_axis[0]), float(cs.x_axis[1]), float(cs.x_axis[2])),
        "y_axis": (float(cs.y_axis[0]), float(cs.y_axis[1]), float(cs.y_axis[2])),
        "z_axis": (float(cs.z_axis[0]), float(cs.z_axis[1]), float(cs.z_axis[2])),
    }


def _attach_track_summary(
    shape: AnyShape,
    *,
    op: str,
    delta: Optional[object] = None,
    delta_entries: Optional[Dict[str, Dict[str, object]]] = None,
) -> AnyShape:
    track_payload: Dict[str, object] = {"op": op}
    if delta is not None:
        track_payload["has_delta"] = True
        track_payload["preserved"] = len(getattr(delta, "preserved", ()))
        track_payload["modified"] = len(getattr(delta, "modified", ()))
        track_payload["generated"] = len(getattr(delta, "generated", ()))
        track_payload["deleted"] = len(getattr(delta, "deleted", ()))
    if delta_entries:
        track_payload["entry_count"] = len(delta_entries)
    shape.set_metadata("track", track_payload)
    return shape


def _vector_like_to_tuple(value: Any) -> Optional[Tuple[float, float, float]]:
    if value is None:
        return None
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        return (float(value.x), float(value.y), float(value.z))
    if isinstance(value, (list, tuple)) and len(value) == 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    return None


def _make_selector_hint(shape: AnyShape) -> Dict[str, object]:
    hint: Dict[str, object] = {
        "kind": type(shape).__name__.lower(),
        "tags": shape._list_tags(),
    }

    if isinstance(shape, Edge):
        hint["length"] = float(shape.get_length())
        try:
            hint["start"] = tuple(
                float(v) for v in shape.get_start_vertex().get_coordinates()
            )
            hint["end"] = tuple(
                float(v) for v in shape.get_end_vertex().get_coordinates()
            )
        except Exception:
            center = getattr(shape.wrapped, "Center", lambda: None)()
            center_tuple = _vector_like_to_tuple(center)
            if center_tuple is not None:
                hint["center"] = center_tuple
    elif isinstance(shape, Face):
        hint["area"] = float(shape.get_area())
        center_tuple = _vector_like_to_tuple(shape.get_center())
        normal_tuple = _vector_like_to_tuple(shape.get_normal_at())
        if center_tuple is not None:
            hint["center"] = center_tuple
        if normal_tuple is not None:
            hint["normal"] = normal_tuple
    elif isinstance(shape, Wire):
        hint["edge_count"] = len(shape.get_edges())
        hint["closed"] = bool(shape.is_closed())
    elif isinstance(shape, Vertex):
        hint["coordinates"] = tuple(float(v) for v in shape.get_coordinates())
    elif isinstance(shape, Solid):
        hint["volume"] = float(shape.get_volume())
        bb = bounding_box(shape.wrapped)
        hint["bbox"] = {
            "min": (float(bb.xmin), float(bb.ymin), float(bb.zmin)),
            "max": (float(bb.xmax), float(bb.ymax), float(bb.zmax)),
        }
    elif isinstance(shape, Compound):
        hint["volume"] = float(shape.get_volume())
        hint["solid_count"] = len(shape.get_solids())
        bb = bounding_box(shape.wrapped)
        hint["bbox"] = {
            "min": (float(bb.xmin), float(bb.ymin), float(bb.zmin)),
            "max": (float(bb.xmax), float(bb.ymax), float(bb.zmax)),
        }

    return hint


def _jsonable_geo_value(value: object) -> object:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        return float(value)
    if isinstance(value, (int, float)):
        return value
    if hasattr(value, "to_tuple"):
        try:
            return [float(v) for v in value.to_tuple()]
        except Exception:
            pass
    if hasattr(value, "x") and hasattr(value, "y") and hasattr(value, "z"):
        try:
            return [float(value.x), float(value.y), float(value.z)]
        except Exception:
            pass
    if isinstance(value, dict):
        return {str(k): _jsonable_geo_value(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable_geo_value(v) for v in value]
    return str(value)


def _bbox_selector_payload(shape: AnyShape) -> Optional[Dict[str, List[float]]]:
    try:
        bb = bounding_box(shape.wrapped)
        return {
            "min": [float(bb.xmin), float(bb.ymin), float(bb.zmin)],
            "max": [float(bb.xmax), float(bb.ymax), float(bb.zmax)],
        }
    except Exception:
        return None


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
                str(surface_type).replace("GeomAbs_SurfaceType.GeomAbs_", "").upper(),
            )
    except Exception:
        return None
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
    if isinstance(shape, Compound):
        return "compound"
    return type(shape).__name__.lower()


def _selection_op_for_shape(shape: AnyShape) -> Optional[str]:
    if isinstance(shape, Vertex):
        return _OP_MAKE_SELECT_RVERTEX
    if isinstance(shape, Edge):
        return _OP_MAKE_SELECT_REDGE
    if isinstance(shape, Wire):
        return _OP_MAKE_SELECT_RWIRE
    if isinstance(shape, Face):
        return _OP_MAKE_SELECT_RFACE
    if isinstance(shape, Solid):
        return _OP_MAKE_SELECT_RSOLID
    return None


def _candidate_shapes_for_selection(source: AnyShape, kind: str) -> List[AnyShape]:
    if kind == "edge":
        if hasattr(source, "get_edges"):
            return list(source.get_edges())
        return [source] if isinstance(source, Edge) else []
    if kind == "face":
        if isinstance(source, (Solid, Compound)):
            return list(source.get_faces())
        return [source] if isinstance(source, Face) else []
    if kind == "wire":
        if isinstance(source, Face):
            return [source.get_outer_wire(), *source.get_inner_wires()]
        if hasattr(source, "get_children"):
            return [
                cast(AnyShape, child)
                for child in source.get_children()
                if isinstance(child, Wire)
            ]
        return [source] if isinstance(source, Wire) else []
    if kind == "vertex":
        if isinstance(source, Edge):
            return cast(List[AnyShape], source.get_children())
        if hasattr(source, "get_children"):
            return [
                cast(AnyShape, child)
                for child in source.get_children()
                if isinstance(child, Vertex)
            ]
        return [source] if isinstance(source, Vertex) else []
    if kind == "solid":
        if isinstance(source, Compound):
            return cast(List[AnyShape], source.get_solids())
        return [source] if isinstance(source, Solid) else []
    if kind == "compound":
        return [source] if isinstance(source, Compound) else []
    return []


def _source_selection_index(
    source: AnyShape, selected: AnyShape, *, kind: str
) -> Optional[int]:
    for idx, candidate in enumerate(_candidate_shapes_for_selection(source, kind)):
        try:
            if candidate.same_topology(selected):
                return idx
        except Exception:
            pass
        if getattr(candidate, "topo_id", None) == getattr(selected, "topo_id", None):
            return idx
    return None


def _make_geo_selector(
    shape: AnyShape,
    *,
    source_shape: Optional[AnyShape] = None,
) -> Dict[str, object]:
    kind = _shape_kind_token(shape)
    selector: Dict[str, object] = {
        "mode": "geo_exact",
        "kind": kind,
        "metadata_geo": _jsonable_geo_value(shape.get_metadata("geo", {})),
    }
    # `source_shape` is intentionally not serialized as a source index. The
    # canonical selector is geometry-based; source lineage comes from graph inputs.

    bbox_payload = _bbox_selector_payload(shape)
    if bbox_payload is not None:
        selector["bbox"] = bbox_payload

    geom_type = _shape_geom_type(shape)
    if geom_type is not None:
        selector["geom_type"] = geom_type

    if isinstance(shape, Vertex):
        selector["coordinates"] = [float(v) for v in shape.get_coordinates()]
    elif isinstance(shape, Edge):
        selector["length"] = float(shape.get_length())
        center = shape.get_center()
        selector["center"] = [float(center.x), float(center.y), float(center.z)]
        try:
            selector["start"] = [
                float(v) for v in shape.get_start_vertex().get_coordinates()
            ]
            selector["end"] = [
                float(v) for v in shape.get_end_vertex().get_coordinates()
            ]
        except Exception:
            pass
    elif isinstance(shape, Wire):
        selector["edge_count"] = len(shape.get_edges())
        selector["closed"] = bool(shape.is_closed())
    elif isinstance(shape, Face):
        selector["area"] = float(shape.get_area())
        center = shape.get_center()
        normal = shape.get_normal_at()
        selector["center"] = [float(center.x), float(center.y), float(center.z)]
        selector["normal"] = [float(normal.x), float(normal.y), float(normal.z)]
        selector["edge_count"] = len(shape.get_edges())
        selector["inner_wire_count"] = len(shape.get_inner_wires())
    elif isinstance(shape, Solid):
        selector["volume"] = float(shape.get_volume())
        center = shape.get_center() if hasattr(shape, "get_center") else None
        if center is not None:
            selector["center"] = [float(center.x), float(center.y), float(center.z)]
    elif isinstance(shape, Compound):
        selector["volume"] = float(shape.get_volume())
        selector["solid_count"] = len(shape.get_solids())
    return selector


def _record_geo_selection_nodes(
    source_shape: AnyShape,
    selected_shapes: Sequence[AnyShape],
) -> List[str]:
    session = get_active_session()
    if session is None:
        return []
    source_node = source_shape._get_runtime("graph.node")
    if source_node is None:
        return []

    node_ids: List[str] = []
    for selected in selected_shapes:
        op = _selection_op_for_shape(selected)
        if op is None:
            continue
        kind = _shape_kind_token(selected)
        selected_node = _active_graph_node_for_shape(selected)
        inputs = [source_node]
        if (
            selected_node is not None
            and getattr(selected_node, "op", None) == _OP_APPLY_TAG_RSELECTION
            and selected_node is not source_node
        ):
            inputs.append(selected_node)
        node = record_operation(
            op=op,
            params={
                "target_kind": kind,
                "geo_selector": _make_geo_selector(
                    selected,
                    source_shape=source_shape,
                ),
            },
            inputs=inputs,
            output_count=1,
            semantic_delta=_semantic_delta_for_output(op, entity_type="Selection"),
            context=_current_context_metadata(),
        )
        attach_graph_node(
            selected,
            node,
            output_slot=0,
            graph_id=session.graph.graph_id,
        )
        node_ids.append(node.node_id)
    return node_ids


_GEO_SELECT_OPS = {
    _OP_MAKE_SELECT_RVERTEX,
    _OP_MAKE_SELECT_REDGE,
    _OP_MAKE_SELECT_RWIRE,
    _OP_MAKE_SELECT_RFACE,
    _OP_MAKE_SELECT_RSOLID,
}


def _is_geo_select_node(node: object) -> bool:
    return getattr(node, "op", None) in _GEO_SELECT_OPS


def _ensure_source_shape_has_own_selection_node(
    source_shape: AnyShape,
) -> Optional[object]:
    source_node = _active_graph_node_for_shape(source_shape)
    if (
        source_node is None
        or _is_geo_select_node(source_node)
        or getattr(source_node, "op", None) == _OP_APPLY_TAG_RSELECTION
    ):
        return source_node

    parent_source = _selection_source_for_shape(source_shape)
    if parent_source is None:
        return source_node

    _ensure_geo_selection_node_ids(parent_source, [source_shape])
    return _active_graph_node_for_shape(source_shape)


def _ensure_geo_selection_node_ids(
    source_shape: AnyShape,
    selected_shapes: Sequence[AnyShape],
) -> List[str]:
    session = get_active_session()
    if session is None:
        return []
    source_node = _ensure_source_shape_has_own_selection_node(source_shape)
    if source_node is None:
        return []

    node_ids: List[str] = []
    for selected in selected_shapes:
        existing_node = _active_graph_node_for_shape(selected)
        existing_op = getattr(existing_node, "op", None)
        if existing_node is not None and existing_op in _GEO_SELECT_OPS:
            node_ids.append(str(existing_node.node_id))
            continue
        node_ids.extend(_record_geo_selection_nodes(source_shape, [selected]))
    return node_ids


def _active_graph_node_for_shape(shape: AnyShape) -> Optional[object]:
    session = get_active_session()
    if session is None:
        return None
    node = shape._get_runtime("graph.node")
    node_id = getattr(node, "node_id", None)
    if node_id is None:
        return None
    if session.graph.get_node(str(node_id)) is None:
        return None
    return node


def _parent_shapes(shape: AnyShape) -> List[AnyShape]:
    parents: List[AnyShape] = []
    get_parent = getattr(shape, "get_parent", None)
    if callable(get_parent):
        parent = get_parent()
        if parent is not None:
            parents.append(cast(AnyShape, parent))
    get_parents = getattr(shape, "get_parents", None)
    if callable(get_parents):
        for parent in get_parents():
            if parent is not None:
                parents.append(cast(AnyShape, parent))
    return parents


def _selection_source_for_shape(shape: AnyShape) -> Optional[AnyShape]:
    kind = _shape_kind_token(shape)
    seen: Set[int] = set()
    stack = _parent_shapes(shape)

    while stack:
        source = stack.pop(0)
        marker = id(source)
        if marker in seen or source is shape:
            continue
        seen.add(marker)

        if _source_selection_index(source, shape, kind=kind) is not None:
            if _active_graph_node_for_shape(source) is not None:
                return source

        stack.extend(_parent_shapes(source))

    return None


def _ensure_geo_selection_input_nodes(
    input_shapes: Optional[Sequence[AnyShape]],
) -> Optional[Sequence[AnyShape]]:
    if not input_shapes:
        return input_shapes

    for shape in input_shapes:
        if _active_graph_node_for_shape(shape) is not None:
            continue
        source = _selection_source_for_shape(shape)
        if source is not None:
            _ensure_geo_selection_node_ids(source, [shape])
    return input_shapes


def _serialize_shape_ref(shape: AnyShape) -> Optional[Dict[str, object]]:
    topo_ref = shape._get_runtime("topo.ref")
    if isinstance(topo_ref, TopoRef):
        data = cast(Dict[str, object], topo_ref_to_dict(topo_ref))
        data["selector_hint"] = _make_selector_hint(shape)
        return data

    topo_ref_meta = shape.get_metadata("topo_ref")
    if isinstance(topo_ref_meta, dict):
        data = cast(Dict[str, object], dict(topo_ref_meta))
        data["selector_hint"] = _make_selector_hint(shape)
        return data

    return None


def _serialize_shape_refs(shapes: Sequence[AnyShape]) -> List[Dict[str, object]]:
    refs: List[Dict[str, object]] = []
    for shape in shapes:
        ref = _serialize_shape_ref(shape)
        if ref is not None:
            refs.append(ref)
    return refs


def _shape_ref_topo_id(shape: AnyShape) -> Optional[str]:
    ref = _serialize_shape_ref(shape)
    if ref is None:
        return None
    topo_id = ref.get("topo_id")
    return str(topo_id) if topo_id is not None else None


def _serialize_selection_indices(
    selected_shapes: Sequence[AnyShape],
    candidates: Sequence[AnyShape],
) -> List[int]:
    candidate_index_by_topo_id: Dict[str, int] = {}
    for idx, candidate in enumerate(candidates):
        topo_id = _shape_ref_topo_id(candidate)
        if topo_id is not None and topo_id not in candidate_index_by_topo_id:
            candidate_index_by_topo_id[topo_id] = idx

    result: List[int] = []
    for selected in selected_shapes:
        topo_id = _shape_ref_topo_id(selected)
        if topo_id is None:
            continue
        if topo_id in candidate_index_by_topo_id:
            result.append(candidate_index_by_topo_id[topo_id])
    return result


def _resolve_selector_or_shapes(
    scope: AnyShape,
    selection: Union[Sequence[AnyShape], ShapeSelector],
) -> List[AnyShape]:
    if isinstance(selection, ShapeSelector):
        return cast(List[AnyShape], selection.resolve(scope))
    return list(selection)


def _semantic_delta_for_output(
    op: str, output_count: int = 1, entity_type: Optional[str] = None
) -> SemanticDelta:
    resolved_entity_type = entity_type
    if resolved_entity_type is None:
        if op in {
            "make_point",
            _OP_MAKE_POINT_RVERTEX,
        }:
            resolved_entity_type = "Point"
        elif op in {
            _OP_MAKE_SKETCH_RSKETCH,
            _OP_MAKE_ADD_POINT_RSKETCH,
            _OP_MAKE_ADD_LINE_RSKETCH,
            _OP_MAKE_ADD_CIRCLE_RSKETCH,
            _OP_MAKE_WIRE_FROM_SKETCH_RWIRE,
            _OP_MAKE_FACE_FROM_SKETCH_RFACE,
            *_SKETCH_CONSTRAINT_OPS.values(),
        }:
            resolved_entity_type = "Sketch"
        elif op in {
            "make_line",
            "make_circle_edge",
            "make_circle_wire",
            "make_circle_face",
            "make_rectangle_wire",
            "make_rectangle_face",
            "make_segment_wire",
            "make_three_point_arc",
            "make_three_point_arc_wire",
            "make_angle_arc",
            "make_angle_arc_wire",
            "make_spline",
            "make_spline_wire",
            "make_polyline_wire",
            "make_helix",
            "make_helix_wire",
            "make_face_from_wire",
            "make_wire_from_edges",
            _OP_MAKE_LINE_REDGE,
            _OP_MAKE_CIRCLE_REDGE,
            _OP_MAKE_THREE_POINT_ARC_REDGE,
            _OP_MAKE_ANGLE_ARC_REDGE,
            _OP_MAKE_SPLINE_REDGE,
            _OP_MAKE_HELIX_REDGE,
            _OP_MAKE_FACE_FROM_WIRE_RFACE,
            _OP_MAKE_WIRE_FROM_EDGES_RWIRE,
        }:
            if op.endswith("_face") or op in {
                "make_face_from_wire",
                _OP_MAKE_FACE_FROM_WIRE_RFACE,
            }:
                resolved_entity_type = "Sketch"
            else:
                resolved_entity_type = "Profile"
        elif op in {
            "make_box",
            "make_cylinder",
            "make_cone",
            "make_sphere",
            "make_box_rsolid",
            "make_cylinder_rsolid",
            "make_cone_rsolid",
            "make_sphere_rsolid",
            "extrude",
            "revolve",
            "loft",
            "sweep",
            "helical_sweep",
            "fillet",
            "chamfer",
            "shell",
            "cut",
            "union",
            "intersect",
            "translate",
            "rotate",
            "mirror",
            _OP_MAKE_EXTRUDE_RSOLID,
            _OP_MAKE_REVOLVE_RSOLID,
            _OP_MAKE_LOFT_RSOLID,
            _OP_MAKE_SWEEP_RSOLID,
            _OP_MAKE_FILLET_RSOLID,
            _OP_MAKE_CHAMFER_RSOLID,
            _OP_MAKE_SHELL_RSOLID,
            _OP_MAKE_CUT_RSOLID,
            _OP_MAKE_UNION_RSOLID,
            _OP_MAKE_INTERSECT_RSOLID,
            _OP_MAKE_TRANSLATE_RSHAPE,
            _OP_MAKE_ROTATE_RSHAPE,
            _OP_MAKE_MIRROR_RSHAPE,
        }:
            if op in {
                "extrude",
                "revolve",
                "loft",
                "sweep",
                "fillet",
                "chamfer",
                "shell",
                "cut",
                "union",
                "intersect",
                _OP_MAKE_EXTRUDE_RSOLID,
                _OP_MAKE_REVOLVE_RSOLID,
                _OP_MAKE_LOFT_RSOLID,
                _OP_MAKE_SWEEP_RSOLID,
                _OP_MAKE_FILLET_RSOLID,
                _OP_MAKE_CHAMFER_RSOLID,
                _OP_MAKE_SHELL_RSOLID,
                _OP_MAKE_CUT_RSOLID,
                _OP_MAKE_UNION_RSOLID,
                _OP_MAKE_INTERSECT_RSOLID,
            }:
                resolved_entity_type = "Feature"
            else:
                resolved_entity_type = "Body"
        else:
            resolved_entity_type = "ShapeOutput"

    refs = tuple(
        SemanticRef(
            graph_id="pending",
            node_id="pending",
            entity_type=resolved_entity_type,
            entity_id=f"{op}:{slot}",
        )
        for slot in range(output_count)
    )
    return SemanticDelta(created=refs, metadata={"op": op})


def _finalize_primitive_shape(
    shape: AnyShape,
    *,
    op: str,
    params: Dict[str, object],
    tags: Optional[Set[str]] = None,
) -> AnyShape:
    _attach_track_summary(shape, op=op)
    record_operation_if_active(
        op=op,
        params=params,
        outputs=shape,
        semantic_delta=_semantic_delta_for_output(op),
        context=_current_context_metadata(),
        tags=tags,
    )
    return shape


def _finalize_primitive_solid(
    solid: Solid,
    *,
    op: str,
    params: Dict[str, object],
    tags: Optional[Set[str]] = None,
) -> Solid:
    return cast(
        Solid,
        _finalize_primitive_shape(solid, op=op, params=params, tags=tags),
    )


def _finalize_derived_shape(
    shape: AnyShape,
    *,
    op: str,
    params: Dict[str, object],
    input_shapes: Sequence[AnyShape],
    tags: Optional[Set[str]] = None,
) -> AnyShape:
    _attach_track_summary(shape, op=op)
    record_operation_if_active(
        op=op,
        params=params,
        outputs=shape,
        input_shapes=_ensure_geo_selection_input_nodes(input_shapes),
        semantic_delta=_semantic_delta_for_output(op),
        context=_current_context_metadata(),
        tags=tags,
    )
    return shape


def _finalize_runtime_object(
    output: object,
    *,
    op: str,
    params: Dict[str, object],
    input_objects: Optional[Sequence[object]] = None,
    tags: Optional[Set[str]] = None,
    entity_type: str = "Sketch",
) -> object:
    record_operation_if_active(
        op=op,
        params=params,
        outputs=output,
        input_shapes=input_objects,
        semantic_delta=_semantic_delta_for_output(op, entity_type=entity_type),
        context=_current_context_metadata(),
        tags=tags,
    )
    return output


def _finalize_tracked_solid(
    solid: Solid,
    *,
    op: str,
    params: Dict[str, object],
    source_solid: Optional[Solid] = None,
    source_solids: Optional[Sequence[Solid]] = None,
    delta: Optional[object] = None,
    delta_entries: Optional[Dict[str, Dict[str, object]]] = None,
    input_shapes: Optional[Sequence[AnyShape]] = None,
) -> Solid:
    if delta is not None:
        apply_tracking_tags_to_delta(
            solid,
            cast(TopoDelta, delta),
            cast(Optional[Dict[str, Dict[str, Any]]], delta_entries),
            op=op,
            source_solid=source_solid,
            source_solids=source_solids,
            source_shapes=input_shapes,
        )
    _attach_track_summary(
        solid,
        op=op,
        delta=delta,
        delta_entries=delta_entries,
    )
    record_operation_if_active(
        op=op,
        params=params,
        outputs=solid,
        input_shapes=_ensure_geo_selection_input_nodes(input_shapes),
        semantic_delta=_semantic_delta_for_output(op),
        topo_delta=cast(Optional[TopoDelta], delta),
        context=_current_context_metadata(),
    )
    return solid


def _normalize_operation_output_tags(
    op: str,
    output_tags: Optional[Mapping[str, str]],
    named_tags: Sequence[Tuple[str, Optional[str]]],
) -> List[Tuple[str, str, str]]:
    role_specs = _OPERATION_OUTPUT_ROLE_CARDINALITY[op]
    cardinality_by_role = dict(role_specs)
    requested: Dict[str, str] = {}

    if output_tags is not None:
        if not isinstance(output_tags, Mapping):
            raise TypeError("output_tags must be a mapping of operation role to tag")
        for raw_role, raw_tag in output_tags.items():
            if not isinstance(raw_role, str) or not raw_role.strip():
                raise ValueError("output tag roles must be non-empty strings")
            role = raw_role.strip().lower()
            if role in requested:
                raise ValueError(f"duplicate output tag role: {role}")
            requested[role] = normalize_tag(raw_tag, strict=True)

    for role, raw_tag in named_tags:
        if raw_tag is None:
            continue
        if role in requested:
            raise ValueError(
                f"output role '{role}' was supplied through both output_tags and a named tag argument"
            )
        requested[role] = normalize_tag(raw_tag, strict=True)

    unknown = sorted(set(requested) - set(cardinality_by_role))
    if unknown:
        raise ValueError(
            f"unsupported output role(s) for {op}: {', '.join(unknown)}; "
            f"expected one of {', '.join(cardinality_by_role)}"
        )
    return [
        (role, cardinality, requested[role])
        for role, cardinality in role_specs
        if role in requested
    ]


def _validate_operation_output_roles(
    delta: TopoDelta,
    assignments: Sequence[Tuple[str, str, str]],
) -> Dict[str, str]:
    target_kinds: Dict[str, str] = {}
    for role, cardinality, _tag in assignments:
        role_entries = {
            (entry.ref, entry.ref.kind.name.lower())
            for entry in delta.roles
            if entry.role == role
            and str(entry.metadata.get("coverage", "complete")).lower() == "complete"
            and str(entry.metadata.get("status", "proven")).lower() == "proven"
        }
        refs = {ref for ref, _kind in role_entries}
        kinds = {kind for _ref, kind in role_entries}
        if cardinality == "one" and len(refs) != 1:
            raise SemanticCapabilityError(
                f"operation output role '{role}' requires exactly one kernel-proven result, got {len(refs)}"
            )
        if cardinality == "many" and not refs:
            raise SemanticCapabilityError(
                f"operation output role '{role}' requires at least one kernel-proven result"
            )
        if len(kinds) != 1:
            raise SemanticCapabilityError(
                f"operation output role '{role}' does not resolve to one topology kind"
            )
        target_kinds[role] = next(iter(kinds))
    return target_kinds


def _apply_operation_output_tags(
    solid: Solid,
    *,
    op: str,
    assignments: Sequence[Tuple[str, str, str]],
    target_kinds: Mapping[str, str],
    result_tag: Optional[str] = None,
) -> Solid:
    if not assignments and result_tag is None:
        return solid

    role_source_node = _active_graph_node_for_shape(solid)
    role_source_slot = int(solid._get_runtime("graph.output_slot", 0))
    result: AnyShape = solid
    for role, cardinality, tag in assignments:
        selector = ShapeSelector(target_kinds[role]).where(output_role(role))
        selector = selector.exactly(1) if cardinality == "one" else selector.at_least(1)
        result = _apply_tag_rselection(
            result,
            selector,
            tag,
            TopologyPropagation.LOCAL,
            LineagePolicy.CONTINUATION_FRAGMENT,
            authoring_source=f"simplecadapi.{op}.output_tags",
            extra_evidence={
                "operation_output_role": {
                    "source_node_id": (
                        role_source_node.node_id
                        if role_source_node is not None
                        else None
                    ),
                    "source_output_slot": role_source_slot,
                    "operation": op,
                    "role": role,
                    "cardinality": cardinality,
                }
            },
        )
    if result_tag is not None:
        result = _apply_tag_rselection(
            result,
            ShapeSelector("solid").exactly(1),
            result_tag,
            TopologyPropagation.LOCAL,
            LineagePolicy.CONTINUATION_FRAGMENT,
            authoring_source=f"simplecadapi.{op}.result_tag",
            extra_evidence={
                "operation_result": {
                    "source_node_id": (
                        role_source_node.node_id
                        if role_source_node is not None
                        else None
                    ),
                    "source_output_slot": role_source_slot,
                    "operation": op,
                }
            },
        )
    return cast(Solid, result)


# =============================================================================
# 基础图形创建函数
# =============================================================================


def make_point_rvertex(x: ScalarLike, y: ScalarLike, z: ScalarLike) -> Vertex:
    """Create a point in 3D space and return it as a vertex."""
    try:
        cs = get_current_cs()
        point_value = cast(Tuple[float, float, float], evaluate_value((x, y, z)))
        global_point = cs.transform_point(np.array(point_value))
        vertex_shape = BRepBuilderAPI_MakeVertex(
            gp_Pnt(
                float(global_point[0]), float(global_point[1]), float(global_point[2])
            )
        ).Vertex()
        return cast(
            Vertex,
            _finalize_primitive_shape(
                Vertex(vertex_shape),
                op=_OP_MAKE_POINT_RVERTEX,
                params={"x": x, "y": y, "z": z},
                tags={"primitive", "vertex"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_point_rvertex",
            what_happened="Failed to create a point vertex.",
            possible_causes=[
                "One or more coordinate values are not valid finite scalars.",
                "The current coordinate system rejected the transformed point.",
            ],
            how_to_fix=[
                "Pass numeric x, y, and z values or valid scalar expressions.",
                "Inspect the coordinate values and the active workplane before retrying.",
            ],
            error=e,
        )


def make_sketch_rsketch(
    name: Optional[str] = None,
    *,
    plane: Any = "XY",
    sketch_id: Optional[str] = None,
) -> Sketch:
    """Create an empty declarative sketch document.

    Use this API, not concrete edge/wire constructors, when the intent is to
    build a sketch profile with constraints.
    """
    try:
        sketch = Sketch(name=name, plane=plane, sketch_id=sketch_id)
        return cast(
            Sketch,
            _finalize_runtime_object(
                sketch,
                op=_OP_MAKE_SKETCH_RSKETCH,
                params={"name": name, "plane": plane, "sketch_id": sketch.sketch_id},
                tags={"sketch"},
                entity_type="Sketch",
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_sketch_rsketch",
            what_happened="Failed to create a sketch document.",
            possible_causes=["The sketch name or plane payload is invalid."],
            how_to_fix=["Use plane='XY', 'XZ', 'YZ', or a valid plane mapping."],
            error=e,
        )


def _safe_semantic_tag(prefix: str, value: object) -> str:
    raw = str(value or "unnamed").strip().lower()
    raw = re.sub(r"[^a-z0-9_-]+", ".", raw).strip(".")
    raw = re.sub(r"\.+", ".", raw)
    segments: List[str] = []
    for segment in raw.split("."):
        if not segment:
            continue
        if not segment[0].isalpha():
            segment = f"id_{segment}"
        segments.append(segment)
    if not segments:
        segments = ["unnamed"]
    return normalize_tag(f"{prefix}.{'.'.join(segments)}", strict=True)


def _sketch_target_to_path(target: SketchRef) -> str:
    if target.kind == "point" and target.subentity != "geometry":
        return f"{target.entity_id}.{target.subentity}"
    return target.entity_id


def _resolve_sketch_target(
    sketch: Sketch,
    target: Union[SketchRef, str],
    *,
    expected: Optional[Union[str, Sequence[str]]] = None,
) -> SketchRef:
    return sketch.resolve_target(target, expected=expected)


def _resolve_sketch_targets(
    sketch: Sketch,
    targets: Sequence[Union[SketchRef, str]],
    *,
    expected: Optional[Sequence[Optional[Union[str, Sequence[str]]]]] = None,
) -> List[SketchRef]:
    refs: List[SketchRef] = []
    for index, target in enumerate(targets):
        target_expected = expected[index] if expected is not None else None
        refs.append(_resolve_sketch_target(sketch, target, expected=target_expected))
    return refs


def add_point_rsketch(
    sketch: Sketch,
    point_id: str,
    x: ScalarLike,
    y: ScalarLike,
) -> Sketch:
    """Add a named point entity and return an updated sketch document."""
    try:
        updated = sketch.clone(include_solve=False)
        updated.add_point(point_id, x, y)
        return cast(
            Sketch,
            _finalize_runtime_object(
                updated,
                op=_OP_MAKE_ADD_POINT_RSKETCH,
                params={
                    "sketch_id": updated.sketch_id,
                    "point_id": point_id,
                    "x": x,
                    "y": y,
                },
                input_objects=[sketch],
                tags={"sketch", "point"},
                entity_type="Sketch",
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="add_point_rsketch",
            what_happened="Failed to add a point to the sketch.",
            possible_causes=[
                "The sketch is invalid.",
                "The point id is duplicated.",
                "The x or y value is not a valid scalar or expression.",
            ],
            how_to_fix=[
                "Use a unique point id within the sketch.",
                "Pass numeric x/y values or valid scalar expressions.",
            ],
            error=e,
        )


def get_sketch_entity_rsketchref(
    sketch: Sketch,
    entity_id: str,
) -> SketchRef:
    """Return a stable ref for a named sketch entity."""
    return sketch.ref(entity_id)


def get_sketch_point_rsketchref(
    sketch: Sketch,
    point_path: str,
) -> SketchRef:
    """Return a stable ref for a sketch point or endpoint path."""
    return sketch.point_ref(point_path)


def add_line_rsketch(
    sketch: Sketch,
    entity_id: str,
    start: Union[SketchRef, str],
    end: Union[SketchRef, str],
    *,
    construction: bool = False,
) -> Sketch:
    """Add a named line entity and return an updated sketch document."""
    try:
        start_ref = _resolve_sketch_target(sketch, start, expected="point")
        end_ref = _resolve_sketch_target(sketch, end, expected="point")
        updated = sketch.clone(include_solve=False)
        updated.add_line(entity_id, start_ref, end_ref, construction=construction)
        return cast(
            Sketch,
            _finalize_runtime_object(
                updated,
                op=_OP_MAKE_ADD_LINE_RSKETCH,
                params={
                    "sketch_id": updated.sketch_id,
                    "entity_id": entity_id,
                    "start": _sketch_target_to_path(start_ref),
                    "end": _sketch_target_to_path(end_ref),
                    "construction": construction,
                },
                input_objects=[sketch],
                tags={"sketch", "line"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="add_line_rsketch",
            what_happened="Failed to add a line to the sketch.",
            possible_causes=[
                "The line id is duplicated.",
                "One of the endpoint refs does not belong to this sketch.",
                "Both endpoints resolve to the same point.",
            ],
            how_to_fix=[
                "Use a unique line id.",
                "Create endpoints with add_point_rsketch(...) and refer to them by id.",
            ],
            error=e,
        )


def add_circle_rsketch(
    sketch: Sketch,
    entity_id: str,
    center: Union[SketchRef, str],
    radius: ScalarLike,
    *,
    construction: bool = False,
) -> Sketch:
    """Add a named circle entity and return an updated sketch document."""
    try:
        center_ref = _resolve_sketch_target(sketch, center, expected="point")
        updated = sketch.clone(include_solve=False)
        updated.add_circle(entity_id, center_ref, radius, construction=construction)
        return cast(
            Sketch,
            _finalize_runtime_object(
                updated,
                op=_OP_MAKE_ADD_CIRCLE_RSKETCH,
                params={
                    "sketch_id": updated.sketch_id,
                    "entity_id": entity_id,
                    "center": _sketch_target_to_path(center_ref),
                    "radius": radius,
                    "construction": construction,
                },
                input_objects=[sketch],
                tags={"sketch", "circle"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="add_circle_rsketch",
            what_happened="Failed to add a circle to the sketch.",
            possible_causes=[
                "The circle id is duplicated.",
                "The center ref does not belong to this sketch.",
                "The radius is not positive.",
            ],
            how_to_fix=[
                "Use a unique circle id and a positive radius.",
                "Create the center with add_point_rsketch(...) and refer to it by id.",
            ],
            error=e,
        )


def add_bspline_rsketch(
    sketch: Sketch,
    entity_id: str,
    start: Union[SketchRef, str],
    end: Union[SketchRef, str],
    control_points: Sequence[Sequence[float]],
    degree: int = 3,
    knots: Optional[Sequence[float]] = None,
    multiplicities: Optional[Sequence[int]] = None,
    weights: Optional[Sequence[float]] = None,
    periodic: bool = False,
    *,
    construction: bool = False,
) -> Sketch:
    """Add a B-spline curve entity to a sketch.

    The start/end point refs link the B-spline into a closed profile
    loop.  Control points are stored as literal 2-D coordinates.
    """
    try:
        start_ref = _resolve_sketch_target(sketch, start, expected="point")
        end_ref = _resolve_sketch_target(sketch, end, expected="point")
        updated = sketch.clone(include_solve=False)
        updated.add_bspline(
            entity_id,
            start_ref,
            end_ref,
            control_points=control_points,
            degree=degree,
            knots=knots,
            multiplicities=multiplicities,
            weights=weights,
            periodic=periodic,
            construction=construction,
        )
        bspline_data = updated.entities[str(entity_id)].data
        return cast(
            Sketch,
            _finalize_runtime_object(
                updated,
                op="make_add_bspline_rsketch",
                params={
                    "sketch_id": updated.sketch_id,
                    "entity_id": entity_id,
                    "start": _sketch_target_to_path(start_ref),
                    "end": _sketch_target_to_path(end_ref),
                    "control_points": bspline_data["control_points"],
                    "degree": bspline_data["degree"],
                    "knots": bspline_data["knots"],
                    "multiplicities": bspline_data["multiplicities"],
                    "weights": bspline_data["weights"],
                    "periodic": bspline_data["periodic"],
                    "construction": construction,
                },
                input_objects=[sketch],
                tags={"sketch", "bspline"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="add_bspline_rsketch",
            what_happened="Failed to add a B-spline to the sketch.",
            possible_causes=[
                "The entity id is duplicated.",
                "The start or end ref does not belong to this sketch.",
                "Too few control points for the requested degree.",
            ],
            how_to_fix=[
                "Use a unique entity id.",
                "Create start and end points with add_point_rsketch(...) first.",
                "Pass at least degree+1 control points.",
            ],
            error=e,
        )


def add_arc_rsketch(
    sketch: Sketch,
    entity_id: str,
    start: Union[SketchRef, str],
    end: Union[SketchRef, str],
    center: Union[SketchRef, str],
    *,
    construction: bool = False,
) -> Sketch:
    """Add an arc entity to a sketch."""
    try:
        start_ref = _resolve_sketch_target(sketch, start, expected="point")
        end_ref = _resolve_sketch_target(sketch, end, expected="point")
        center_ref = _resolve_sketch_target(sketch, center, expected="point")
        updated = sketch.clone(include_solve=False)
        updated.add_arc(
            entity_id,
            start_ref,
            end_ref,
            center_ref,
            construction=construction,
        )
        return cast(
            Sketch,
            _finalize_runtime_object(
                updated,
                op="make_add_arc_rsketch",
                params={
                    "sketch_id": updated.sketch_id,
                    "entity_id": entity_id,
                    "start": _sketch_target_to_path(start_ref),
                    "end": _sketch_target_to_path(end_ref),
                    "center": _sketch_target_to_path(center_ref),
                    "construction": construction,
                },
                input_objects=[sketch],
                tags={"sketch", "arc"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="add_arc_rsketch",
            what_happened="Failed to add an arc to the sketch.",
            possible_causes=[
                "The entity id is duplicated.",
                "The start, end, or center ref does not belong to this sketch.",
                "The start and end points are the same.",
            ],
            how_to_fix=[
                "Use a unique entity id.",
                "Create start, end, and center points with add_point_rsketch(...) first.",
            ],
            error=e,
        )


def _constrain_rsketch(
    sketch: Sketch,
    kind: str,
    targets: Sequence[Union[SketchRef, str]],
    *,
    value: Any = None,
    constraint_id: Optional[str] = None,
    driving: bool = True,
    metadata: Optional[Dict[str, Any]] = None,
    expected: Optional[Sequence[Optional[Union[str, Sequence[str]]]]] = None,
) -> Sketch:
    target_refs = _resolve_sketch_targets(sketch, targets, expected=expected)
    updated = sketch.clone(include_solve=False)
    updated.add_constraint(
        kind,
        target_refs,
        value=value,
        constraint_id=constraint_id,
        driving=driving,
        metadata=metadata,
    )
    op = _SKETCH_CONSTRAINT_OPS[kind]
    return cast(
        Sketch,
        _finalize_runtime_object(
            updated,
            op=op,
            params={
                "sketch_id": updated.sketch_id,
                "kind": kind,
                "targets": [_sketch_target_to_path(target) for target in target_refs],
                "value": value,
                "constraint_id": constraint_id,
                "driving": driving,
                "metadata": metadata or {},
            },
            input_objects=[sketch],
            tags={"sketch", "constraint"},
        ),
    )


def constrain_coincident_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Constrain two sketch points to be coincident."""
    return _constrain_rsketch(
        sketch,
        "coincident",
        [a, b],
        constraint_id=constraint_id,
        expected=["point", "point"],
    )


def constrain_connect_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Alias for `constrain_coincident_rsketch` using connection wording."""
    return _constrain_rsketch(
        sketch,
        "coincident",
        [a, b],
        constraint_id=constraint_id,
        expected=["point", "point"],
    )


def constrain_point_on_rsketch(
    sketch: Sketch,
    point: Union[SketchRef, str],
    entity: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Constrain a sketch point to lie on a line or circle."""
    return _constrain_rsketch(
        sketch,
        "point_on",
        [point, entity],
        constraint_id=constraint_id,
        expected=["point", ("line", "circle")],
    )


def constrain_horizontal_rsketch(
    sketch: Sketch, line: Union[SketchRef, str], *, constraint_id: Optional[str] = None
) -> Sketch:
    """Constrain a sketch line to be horizontal."""
    return _constrain_rsketch(
        sketch, "horizontal", [line], constraint_id=constraint_id, expected=["line"]
    )


def constrain_vertical_rsketch(
    sketch: Sketch, line: Union[SketchRef, str], *, constraint_id: Optional[str] = None
) -> Sketch:
    """Constrain a sketch line to be vertical."""
    return _constrain_rsketch(
        sketch, "vertical", [line], constraint_id=constraint_id, expected=["line"]
    )


def constrain_parallel_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Constrain two sketch lines to be parallel."""
    return _constrain_rsketch(
        sketch,
        "parallel",
        [a, b],
        constraint_id=constraint_id,
        expected=["line", "line"],
    )


def constrain_perpendicular_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Constrain two sketch lines to be perpendicular."""
    return _constrain_rsketch(
        sketch,
        "perpendicular",
        [a, b],
        constraint_id=constraint_id,
        expected=["line", "line"],
    )


def constrain_collinear_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Constrain two sketch lines to lie on the same infinite line."""
    return _constrain_rsketch(
        sketch,
        "collinear",
        [a, b],
        constraint_id=constraint_id,
        expected=["line", "line"],
    )


def constrain_tangent_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Constrain supported sketch curves to be tangent."""
    return _constrain_rsketch(
        sketch,
        "tangent",
        [a, b],
        constraint_id=constraint_id,
        expected=[("line", "circle"), ("line", "circle")],
    )


def constrain_concentric_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Constrain two sketch circles to share a center."""
    return _constrain_rsketch(
        sketch,
        "concentric",
        [a, b],
        constraint_id=constraint_id,
        expected=["circle", "circle"],
    )


def constrain_midpoint_rsketch(
    sketch: Sketch,
    point: Union[SketchRef, str],
    line: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Constrain a sketch point to the midpoint of a line."""
    return _constrain_rsketch(
        sketch,
        "midpoint",
        [point, line],
        constraint_id=constraint_id,
        expected=["point", "line"],
    )


def constrain_symmetric_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    axis: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Constrain two sketch points to be symmetric about a line axis."""
    return _constrain_rsketch(
        sketch,
        "symmetric",
        [a, b, axis],
        constraint_id=constraint_id,
        expected=["point", "point", "line"],
    )


def constrain_equal_length_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Constrain two sketch lines to have equal length."""
    return _constrain_rsketch(
        sketch,
        "equal_length",
        [a, b],
        constraint_id=constraint_id,
        expected=["line", "line"],
    )


def constrain_equal_radius_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Constrain two sketch circles to have equal radius."""
    return _constrain_rsketch(
        sketch,
        "equal_radius",
        [a, b],
        constraint_id=constraint_id,
        expected=["circle", "circle"],
    )


def constrain_distance_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    value: ScalarLike,
    *,
    constraint_id: Optional[str] = None,
    driving: bool = True,
) -> Sketch:
    """Add a driving point-to-point distance constraint."""
    return _constrain_rsketch(
        sketch,
        "distance",
        [a, b],
        value=value,
        constraint_id=constraint_id,
        driving=driving,
        expected=["point", "point"],
    )


def constrain_distance_x_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    value: ScalarLike,
    *,
    constraint_id: Optional[str] = None,
    driving: bool = True,
) -> Sketch:
    """Add a driving horizontal distance constraint."""
    return _constrain_rsketch(
        sketch,
        "distance_x",
        [a, b],
        value=value,
        constraint_id=constraint_id,
        driving=driving,
        expected=["point", "point"],
    )


def constrain_distance_y_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    value: ScalarLike,
    *,
    constraint_id: Optional[str] = None,
    driving: bool = True,
) -> Sketch:
    """Add a driving vertical distance constraint."""
    return _constrain_rsketch(
        sketch,
        "distance_y",
        [a, b],
        value=value,
        constraint_id=constraint_id,
        driving=driving,
        expected=["point", "point"],
    )


def constrain_length_rsketch(
    sketch: Sketch,
    line: Union[SketchRef, str],
    value: ScalarLike,
    *,
    constraint_id: Optional[str] = None,
    driving: bool = True,
) -> Sketch:
    """Add a driving line length constraint."""
    return _constrain_rsketch(
        sketch,
        "length",
        [line],
        value=value,
        constraint_id=constraint_id,
        driving=driving,
        expected=["line"],
    )


def constrain_angle_rsketch(
    sketch: Sketch,
    a: Union[SketchRef, str],
    b: Union[SketchRef, str],
    value: ScalarLike,
    *,
    constraint_id: Optional[str] = None,
    driving: bool = True,
) -> Sketch:
    """Add a driving angle constraint between two sketch lines."""
    return _constrain_rsketch(
        sketch,
        "angle",
        [a, b],
        value=value,
        constraint_id=constraint_id,
        driving=driving,
        expected=["line", "line"],
    )


def constrain_radius_rsketch(
    sketch: Sketch,
    circle: Union[SketchRef, str],
    value: ScalarLike,
    *,
    constraint_id: Optional[str] = None,
    driving: bool = True,
) -> Sketch:
    """Add a driving circle radius constraint."""
    return _constrain_rsketch(
        sketch,
        "radius",
        [circle],
        value=value,
        constraint_id=constraint_id,
        driving=driving,
        expected=["circle"],
    )


def constrain_diameter_rsketch(
    sketch: Sketch,
    circle: Union[SketchRef, str],
    value: ScalarLike,
    *,
    constraint_id: Optional[str] = None,
    driving: bool = True,
) -> Sketch:
    """Add a driving circle diameter constraint."""
    return _constrain_rsketch(
        sketch,
        "diameter",
        [circle],
        value=value,
        constraint_id=constraint_id,
        driving=driving,
        expected=["circle"],
    )


def constrain_fix_rsketch(
    sketch: Sketch,
    target: Union[SketchRef, str],
    *,
    constraint_id: Optional[str] = None,
) -> Sketch:
    """Fix a sketch point or entity to its initial coordinates."""
    return _constrain_rsketch(sketch, "fix", [target], constraint_id=constraint_id)


def inspect_sketch_rsketchresult(
    sketch: Sketch,
    *,
    require_fully_constrained: bool = False,
    strict: bool = True,
    tolerance: float = 1e-7,
    max_iterations: int = 80,
) -> SketchSolveResult:
    """Inspect sketch constraints by running the solver without recording graph nodes."""
    try:
        result = sketch.clone(include_solve=False).solve(
            require_fully_constrained=require_fully_constrained,
            strict=strict,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="inspect_sketch_rsketchresult",
            what_happened="Failed to inspect the sketch constraints.",
            possible_causes=[
                "The sketch has invalid, conflicting, or underconstrained constraints.",
                "A constraint references a missing or wrong-kind entity.",
            ],
            how_to_fix=[
                "Inspect diagnostics with strict=False if needed.",
                "Add fix/dimension constraints until the intended profile is fully constrained.",
            ],
            error=e,
        )


def _sketch_solve_snapshot(result: SketchSolveResult) -> Dict[str, Any]:
    return result.to_dict()


def _sketch_source_metadata(
    sketch: Sketch,
    profile: int | str,
    profile_payload: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "sketch_id": sketch.sketch_id,
        "name": sketch.name,
        "plane": sketch.plane,
        "profile": profile,
        "profile_id": profile_payload.get("id"),
        "profile_kind": profile_payload.get("kind"),
    }


def _sketch_edge_metadata(
    sketch: Sketch,
    entity_id: str,
    profile: int | str,
    profile_payload: Dict[str, Any],
) -> Dict[str, Any]:
    entity = sketch.entities[str(entity_id)]
    return {
        "sketch_id": sketch.sketch_id,
        "sketch_name": sketch.name,
        "entity_id": str(entity_id),
        "kind": entity.kind,
        "profile": profile,
        "profile_id": profile_payload.get("id"),
    }


def _sketch_promotion_tags(
    sketch: Sketch,
    profile_payload: Dict[str, Any],
) -> Tuple[str, str]:
    sketch_tag = _safe_semantic_tag("sketch", sketch.name or sketch.sketch_id)
    profile_tag = _safe_semantic_tag(
        "sketch_profile", profile_payload.get("id", "profile")
    )
    return sketch_tag, profile_tag


def _sketch_promotion_map(
    sketch: Sketch,
    profile: int | str,
    profile_payload: Dict[str, Any],
) -> Dict[str, Any]:
    sketch_tag, profile_tag = _sketch_promotion_tags(sketch, profile_payload)
    edges: List[Dict[str, Any]] = []
    for entity_id in profile_payload.get("entity_ids", []):
        entity_tag = _safe_semantic_tag("sketch_entity", entity_id)
        edges.append(
            {
                "entity_id": str(entity_id),
                "target_kind": "edge",
                "tags": [sketch_tag, profile_tag, entity_tag],
                "metadata": {
                    "sketch_ref": _sketch_edge_metadata(
                        sketch, str(entity_id), profile, profile_payload
                    )
                },
            }
        )
    return {
        "profile": profile,
        "profile_id": profile_payload.get("id"),
        "profile_kind": profile_payload.get("kind"),
        "tags": [sketch_tag, profile_tag],
        "edges": edges,
    }


def _apply_sketch_promotion_metadata(
    shape: Union[Wire, Face],
    *,
    sketch: Sketch,
    profile: int | str,
    profile_payload: Dict[str, Any],
    solve_snapshot: Dict[str, Any],
) -> None:
    source_sketch = _sketch_source_metadata(sketch, profile, profile_payload)
    promotion_map = _sketch_promotion_map(sketch, profile, profile_payload)
    sketch_tag, profile_tag = _sketch_promotion_tags(sketch, profile_payload)

    shape.set_metadata("source_sketch", source_sketch)
    shape.set_metadata("sketch_solve", solve_snapshot)
    shape.set_metadata("sketch_promotion", promotion_map)
    shape._apply_tag(sketch_tag, propagate=False)
    shape._apply_tag(profile_tag, propagate=False)

    wires: List[Wire] = []
    if isinstance(shape, Wire):
        wires = [shape]
    elif isinstance(shape, Face):
        wires = cast(List[Wire], shape.get_wires())

    for wire in wires:
        wire.set_metadata("source_sketch", source_sketch)
        wire.set_metadata("sketch_solve", solve_snapshot)
        wire.set_metadata("sketch_promotion", promotion_map)
        wire._apply_tag(sketch_tag, propagate=False)
        wire._apply_tag(profile_tag, propagate=False)

    if isinstance(shape, Face):
        edges = cast(List[Edge], shape.get_edges())
    else:
        edges = cast(List[Edge], shape.get_edges())

    for edge, entity_id in zip(edges, profile_payload.get("entity_ids", [])):
        entity_tag = _safe_semantic_tag("sketch_entity", entity_id)
        edge.set_metadata(
            "sketch_ref",
            _sketch_edge_metadata(sketch, str(entity_id), profile, profile_payload),
        )
        edge.set_metadata("source_sketch", source_sketch)
        edge._apply_tag(sketch_tag, propagate=False)
        edge._apply_tag(profile_tag, propagate=False)
        edge._apply_tag(entity_tag, propagate=False)


def _promote_sketch_profile(
    sketch: Sketch,
    profile: int | str,
    *,
    target_kind: str,
    require_fully_constrained: bool,
    strict: bool,
    tolerance: float,
    max_iterations: int,
) -> Tuple[Union[Wire, Face], SketchSolveResult, Dict[str, Any]]:
    working = sketch.clone(include_solve=False)
    solve_result = working.solve(
        require_fully_constrained=require_fully_constrained,
        strict=strict,
        tolerance=tolerance,
        max_iterations=max_iterations,
    )
    profile_payload = sketch._profile_payload(profile, solve_result=solve_result)
    solve_snapshot = _sketch_solve_snapshot(solve_result)
    with suspend_graph_recording():
        if target_kind == "wire":
            shape = sketch._wire_from_profile_payload(profile_payload)
        elif target_kind == "face":
            wire = sketch._wire_from_profile_payload(profile_payload)
            shape = make_face_from_wire_rface(wire, normal=sketch._plane_normal_tuple())
        else:
            raise ValueError(
                f"Unsupported sketch promotion target kind '{target_kind}'"
            )
    _apply_sketch_promotion_metadata(
        cast(Union[Wire, Face], shape),
        sketch=sketch,
        profile=profile,
        profile_payload=profile_payload,
        solve_snapshot=solve_snapshot,
    )
    return cast(Union[Wire, Face], shape), solve_result, profile_payload


def _assert_sketch_solve_snapshot_matches(
    result: SketchSolveResult,
    snapshot: Dict[str, Any],
    *,
    tolerance: float = 1e-7,
) -> None:
    _assert_sketch_solve_snapshot_dict_matches(
        result.to_dict(), snapshot, tolerance=tolerance
    )


def _assert_sketch_solve_snapshot_dict_matches(
    actual: Dict[str, Any],
    snapshot: Dict[str, Any],
    *,
    tolerance: float = 1e-7,
) -> None:
    if str(actual.get("status")) != str(snapshot.get("status")):
        raise ValueError(
            f"Sketch solve status changed from {snapshot.get('status')!r} to {actual.get('status')!r}"
        )
    if int(actual.get("dof", -1)) != int(snapshot.get("dof", -1)):
        raise ValueError(
            f"Sketch solve DOF changed from {snapshot.get('dof')!r} to {actual.get('dof')!r}"
        )
    if (
        abs(
            float(actual.get("residual_norm", 0.0))
            - float(snapshot.get("residual_norm", 0.0))
        )
        > tolerance
    ):
        raise ValueError("Sketch solve residual changed beyond recorded tolerance")

    actual_points = cast(Dict[str, Any], actual.get("solved_points", {}))
    expected_points = cast(Dict[str, Any], snapshot.get("solved_points", {}))
    if set(actual_points) != set(expected_points):
        raise ValueError("Sketch solve point set changed")
    for point_id, point in actual_points.items():
        expected = expected_points[point_id]
        if (
            math.dist(
                (float(point[0]), float(point[1])),
                (float(expected[0]), float(expected[1])),
            )
            > tolerance
        ):
            raise ValueError(
                f"Sketch solve point '{point_id}' changed beyond recorded tolerance"
            )

    actual_scalars = cast(Dict[str, Any], actual.get("solved_scalars", {}))
    expected_scalars = cast(Dict[str, Any], snapshot.get("solved_scalars", {}))
    if set(actual_scalars) != set(expected_scalars):
        raise ValueError("Sketch solve scalar set changed")
    for scalar_id, value in actual_scalars.items():
        if abs(float(value) - float(expected_scalars[scalar_id])) > tolerance:
            raise ValueError(
                f"Sketch solve scalar '{scalar_id}' changed beyond recorded tolerance"
            )


def make_line_redge(
    start: Tuple[ScalarLike, ScalarLike, ScalarLike],
    end: Tuple[ScalarLike, ScalarLike, ScalarLike],
) -> Edge:
    """Create a straight edge between two points."""
    try:
        cs = get_current_cs()
        start_value = cast(Tuple[float, float, float], evaluate_value(start))
        end_value = cast(Tuple[float, float, float], evaluate_value(end))
        start_global = cs.transform_point(np.array(start_value))
        end_global = cs.transform_point(np.array(end_value))

        edge_shape = make_line_edge(start_global, end_global)
        return cast(
            Edge,
            _finalize_primitive_shape(
                Edge(edge_shape),
                op=_OP_MAKE_LINE_REDGE,
                params={"start": start, "end": end},
                tags={"primitive", "edge"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_line_redge",
            what_happened="Failed to create a line edge.",
            possible_causes=[
                "The start or end point is not a valid finite 3D point.",
                "The transformed points are degenerate or rejected by the kernel.",
            ],
            how_to_fix=[
                "Pass start and end as 3-element numeric tuples or valid expressions.",
                "Ensure the two points are distinct and finite.",
            ],
            error=e,
        )


def make_segment_redge(
    start: Tuple[float, float, float], end: Tuple[float, float, float]
) -> Edge:
    """Alias of `make_line_redge` that returns a straight edge."""
    return make_line_redge(start, end)


def make_segment_rwire(
    start: Tuple[float, float, float], end: Tuple[float, float, float]
) -> Wire:
    """Create a wire containing a single straight segment."""
    try:
        if get_active_session() is not None:
            edge = make_line_redge(start, end)
            return make_wire_from_edges_rwire([edge])

        with suspend_graph_recording():
            edge = make_line_redge(start, end)
        wire_shape = make_wire_from_edges_ocp([edge.wrapped])
        return cast(
            Wire,
            _finalize_primitive_shape(
                Wire(wire_shape),
                op="make_segment_wire",
                params={"start": start, "end": end},
                tags={"primitive", "wire"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_segment_rwire",
            what_happened="Failed to create a single-segment wire.",
            possible_causes=[
                "The segment endpoints are invalid.",
                "The kernel could not assemble the segment into a wire.",
            ],
            how_to_fix=[
                "Pass two valid 3D endpoints.",
                "If the segment is computed dynamically, log the two endpoints before retrying.",
            ],
            error=e,
        )


def make_circle_redge(
    center: Tuple[float, float, float],
    radius: ScalarLike,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Edge:
    """Create a circular edge."""
    try:
        radius_value = evaluate_scalar(radius)
        if radius_value <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        center_value = cast(Tuple[float, float, float], evaluate_value(center))
        normal_value = cast(Tuple[float, float, float], evaluate_value(normal))
        center_global = cs.transform_point(np.array(center_value))
        normal_global = cs.transform_point(np.array(normal_value)) - cs.origin

        edge_shape = make_circle_edge(center_global, radius_value, normal_global)
        return cast(
            Edge,
            _finalize_primitive_shape(
                Edge(edge_shape),
                op=_OP_MAKE_CIRCLE_REDGE,
                params={"center": center, "radius": radius, "normal": normal},
                tags={"primitive", "edge"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_circle_redge",
            what_happened="Failed to create a circular edge.",
            possible_causes=[
                "The radius is not a positive finite scalar.",
                "The center or normal is not a valid finite 3D vector.",
                "The kernel rejected the circle definition.",
            ],
            how_to_fix=[
                "Use a radius greater than zero.",
                "Pass finite center and normal vectors.",
                "If the normal is computed dynamically, verify it is not zero-length.",
            ],
            error=e,
        )


def make_circle_rwire(
    center: Tuple[float, float, float],
    radius: ScalarLike,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Wire:
    """Create a circular wire."""
    try:
        if get_active_session() is not None:
            edge = make_circle_redge(center, radius, normal)
            return make_wire_from_edges_rwire([edge])

        with suspend_graph_recording():
            edge = make_circle_redge(center, radius, normal)
        wire_shape = make_wire_from_edges_ocp([edge.wrapped])
        return cast(
            Wire,
            _finalize_primitive_shape(
                Wire(wire_shape),
                op="make_circle_wire",
                params={"center": center, "radius": radius, "normal": normal},
                tags={"primitive", "wire"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_circle_rwire",
            what_happened="Failed to create a circular wire.",
            possible_causes=[
                "The circle edge could not be created.",
                "The wire assembly step rejected the generated edge.",
            ],
            how_to_fix=[
                "Check the center, radius, and normal inputs.",
                "Retry with a positive radius and a valid normal vector.",
            ],
            error=e,
        )


def make_circle_rface(
    center: Tuple[float, float, float],
    radius: ScalarLike,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Face:
    """Create a circular face."""
    try:
        if get_active_session() is not None:
            wire = make_circle_rwire(center, radius, normal)
            return make_face_from_wire_rface(wire, normal=normal)

        with suspend_graph_recording():
            wire = make_circle_rwire(center, radius, normal)
        face_shape = make_face_from_wire_ocp(wire.wrapped)
        face = Face(face_shape)
        face._metadata = wire._metadata.copy()
        return cast(
            Face,
            _finalize_primitive_shape(
                face,
                op="make_circle_face",
                params={"center": center, "radius": radius, "normal": normal},
                tags={"primitive", "face"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_circle_rface",
            what_happened="Failed to create a circular face.",
            possible_causes=[
                "The underlying circular wire could not be created.",
                "The kernel could not create a face from the wire.",
            ],
            how_to_fix=[
                "Verify the center, radius, and normal values.",
                "Use a positive radius and a valid non-zero normal vector.",
            ],
            error=e,
        )


def make_rectangle_rwire(
    width: ScalarLike,
    height: ScalarLike,
    center: Tuple[ScalarLike, ScalarLike, ScalarLike] = (0, 0, 0),
    normal: Tuple[ScalarLike, ScalarLike, ScalarLike] = (0, 0, 1),
) -> Wire:
    """Create a rectangular wire."""
    try:
        width_value = evaluate_scalar(width)
        height_value = evaluate_scalar(height)
        if width_value <= 0 or height_value <= 0:
            raise ValueError("宽度和高度必须大于0")

        if get_active_session() is not None:
            normal_value = cast(Tuple[float, float, float], evaluate_value(normal))
            _, x_axis, y_axis = _orthonormal_plane_axes(normal_value)
            half_w = width / 2
            half_h = height / 2
            corners = [
                _offset_point_expr(center, x_axis, y_axis, -half_w, -half_h),
                _offset_point_expr(center, x_axis, y_axis, half_w, -half_h),
                _offset_point_expr(center, x_axis, y_axis, half_w, half_h),
                _offset_point_expr(center, x_axis, y_axis, -half_w, half_h),
            ]
            return _make_closed_profile_rwire(corners)

        cs = get_current_cs()
        center_value = cast(Tuple[float, float, float], evaluate_value(center))
        normal_value = cast(Tuple[float, float, float], evaluate_value(normal))
        center_global = cs.transform_point(np.array(center_value))
        normal_global = cs.transform_point(np.array(normal_value)) - cs.origin

        # 标准化法向量
        normal_vec = normal_global / np.linalg.norm(normal_global)

        # 创建本地坐标系
        # 如果法向量接近Z轴，使用X轴作为参考
        if abs(normal_vec[2]) > 0.9:
            ref_vec = np.array([1.0, 0.0, 0.0])
        else:
            ref_vec = np.array([0.0, 0.0, 1.0])

        # 计算本地坐标系的X和Y轴
        local_x = np.cross(normal_vec, ref_vec)
        local_x = local_x / np.linalg.norm(local_x)
        local_y = np.cross(normal_vec, local_x)
        local_y = local_y / np.linalg.norm(local_y)

        # 创建矩形的四个顶点（在本地坐标系中）
        half_w, half_h = width_value / 2, height_value / 2
        local_points = [
            (-half_w, -half_h),
            (half_w, -half_h),
            (half_w, half_h),
            (-half_w, half_h),
        ]

        # 转换到全局坐标系
        global_points = []
        for local_point in local_points:
            # 在本地坐标系中的点
            point_3d = (
                center_global + local_point[0] * local_x + local_point[1] * local_y
            )
            global_points.append(tuple(float(v) for v in point_3d))

        # 创建边
        wire_points = [
            (float(point[0]), float(point[1]), float(point[2]))
            for point in global_points
        ]
        wire_shape = make_polyline_wire(wire_points, closed=True)
        return cast(
            Wire,
            _finalize_primitive_shape(
                Wire(wire_shape),
                op="make_rectangle_wire",
                params={
                    "width": width,
                    "height": height,
                    "center": center,
                    "normal": normal,
                },
                tags={"primitive", "wire"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_rectangle_rwire",
            what_happened="Failed to create a rectangular wire.",
            possible_causes=[
                "Width or height is not a positive finite scalar.",
                "The center or normal is not a valid finite 3D vector.",
                "The local rectangle basis became degenerate.",
            ],
            how_to_fix=[
                "Use width and height values greater than zero.",
                "Pass a valid center and a non-zero normal vector.",
                "If the normal is near zero, normalize or replace it before retrying.",
            ],
            error=e,
        )


def make_rectangle_rface(
    width: ScalarLike,
    height: ScalarLike,
    center: Tuple[ScalarLike, ScalarLike, ScalarLike] = (0, 0, 0),
    normal: Tuple[ScalarLike, ScalarLike, ScalarLike] = (0, 0, 1),
) -> Face:
    """Create a rectangular face."""
    try:
        if get_active_session() is not None:
            wire = make_rectangle_rwire(width, height, center, normal)
            return make_face_from_wire_rface(wire, normal=cast(Any, normal))

        with suspend_graph_recording():
            wire = make_rectangle_rwire(width, height, center, normal)
        face_shape = make_face_from_wire_ocp(wire.wrapped)
        face = Face(face_shape)
        face._metadata = wire._metadata.copy()
        return cast(
            Face,
            _finalize_primitive_shape(
                face,
                op="make_rectangle_face",
                params={
                    "width": width,
                    "height": height,
                    "center": center,
                    "normal": normal,
                },
                tags={"primitive", "face"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_rectangle_rface",
            what_happened="Failed to create a rectangular face.",
            possible_causes=[
                "The rectangular wire could not be created.",
                "The face construction step rejected the generated wire.",
            ],
            how_to_fix=[
                "Verify width, height, center, and normal.",
                "Retry with positive dimensions and a valid non-zero normal vector.",
            ],
            error=e,
        )


def make_face_from_wire_rface(
    wire: Wire, normal: Tuple[float, float, float] = (0, 0, 1)
) -> Face:
    """Create a face from a closed wire."""
    try:
        if not isinstance(wire, Wire):
            raise ValueError("输入必须是Wire类型")

        # 检查Wire是否封闭
        if not wire.is_closed():
            raise ValueError("Wire必须是封闭的才能创建面")

        # 获取当前坐标系并转换法向量
        cs = get_current_cs()
        global_normal = cs.transform_point(np.array(normal)) - cs.origin

        # 标准化法向量
        normal_vec = global_normal / np.linalg.norm(global_normal)

        # 创建面
        face_shape = make_face_from_wire_ocp(wire.wrapped)
        face = Face(face_shape)

        # 检查面的法向量是否与期望方向一致
        face_normal = face.get_normal_at()
        face_normal_vec = np.array([face_normal.x, face_normal.y, face_normal.z])

        # 计算法向量的点积，如果小于0则需要反向
        dot_product = np.dot(normal_vec, face_normal_vec)

        if dot_product < 0:
            # 反向面（通过反向Wire的方向）
            # OCP Wire 没有直接的 reverse 包装方法，这里重新构建
            # 简单的方法是使用makeFromWires的orientation参数
            # 或者我们接受当前面的方向，添加一个警告
            print(f"警告: 创建的面的法向量与期望方向相反 (点积: {dot_product:.3f})")

        face._metadata = wire._metadata.copy()

        return cast(
            Face,
            _finalize_derived_shape(
                face,
                op=_OP_MAKE_FACE_FROM_WIRE_RFACE,
                params={"normal": normal},
                input_shapes=[wire],
                tags={"derived", "face"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_face_from_wire_rface",
            what_happened="Failed to create a face from the input wire.",
            possible_causes=[
                "The input is not a Wire instance.",
                "The wire is open or geometrically invalid.",
                "The kernel rejected the closed wire when building a face.",
            ],
            how_to_fix=[
                "Pass a Wire object, not an Edge or a list of points.",
                "Ensure the wire is closed before calling this API.",
                "If the wire was assembled from edges, verify the edges connect end-to-end.",
            ],
            error=e,
        )


def make_face_from_wires_rface(
    outer_wire: Wire,
    inner_wires: Sequence[Wire],
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Face:
    """Create a face from one outer closed wire and optional inner closed wires."""
    try:
        if not isinstance(outer_wire, Wire):
            raise ValueError("outer_wire must be a Wire")
        if not outer_wire.is_closed():
            raise ValueError("outer_wire must be closed")

        inner_list = list(inner_wires or [])
        for inner_wire in inner_list:
            if not isinstance(inner_wire, Wire):
                raise ValueError("inner_wires must contain only Wire objects")
            if not inner_wire.is_closed():
                raise ValueError("inner wires must be closed")

        cs = get_current_cs()
        global_normal = cs.transform_point(np.array(normal)) - cs.origin
        normal_norm = float(np.linalg.norm(global_normal))
        if normal_norm <= 1e-15 or not np.isfinite(normal_norm):
            raise ValueError("normal must be a non-zero finite vector")
        normal_vec = global_normal / normal_norm

        face_shape = make_face_from_wires_ocp(
            outer_wire.wrapped,
            [inner_wire.wrapped for inner_wire in inner_list],
        )
        face = Face(face_shape)

        face_normal = face.get_normal_at()
        face_normal_vec = np.array([face_normal.x, face_normal.y, face_normal.z])
        dot_product = float(np.dot(normal_vec, face_normal_vec))
        if dot_product < 0:
            print(f"警告: 创建的面的法向量与期望方向相反 (点积: {dot_product:.3f})")

        face._metadata = outer_wire._metadata.copy()

        return cast(
            Face,
            _finalize_derived_shape(
                face,
                op=_OP_MAKE_FACE_FROM_WIRES_RFACE,
                params={"normal": normal, "inner_wire_count": len(inner_list)},
                input_shapes=[outer_wire, *inner_list],
                tags={"derived", "face"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_face_from_wires_rface",
            what_happened="Failed to create a face from the input outer and inner wires.",
            possible_causes=[
                "The outer wire is not a Wire instance or is not closed.",
                "One or more inner wires are not Wire instances or are not closed.",
                "The inner wires are not contained by the outer wire or are geometrically invalid.",
                "The kernel rejected the multi-loop face definition.",
            ],
            how_to_fix=[
                "Pass one closed outer Wire and zero or more closed inner Wire objects.",
                "Ensure every inner wire lies inside the outer wire and does not intersect other loops.",
                "Use a valid non-zero normal vector.",
            ],
            error=e,
        )


def make_wire_from_edges_rwire(edges: List[Edge]) -> Wire:
    """Create a wire from a list of connected edges."""
    try:
        if not edges:
            raise ValueError("边列表不能为空")

        wire_shape = make_wire_from_edges_ocp([edge.wrapped for edge in edges])
        return cast(
            Wire,
            _finalize_derived_shape(
                Wire(wire_shape),
                op=_OP_MAKE_WIRE_FROM_EDGES_RWIRE,
                params={"edge_count": len(edges)},
                input_shapes=edges,
                tags={"derived", "wire"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_wire_from_edges_rwire",
            what_happened="Failed to assemble a wire from the input edges.",
            possible_causes=[
                "The edge list is empty.",
                "One or more items are invalid edges.",
                "The edges do not connect into a valid wire chain.",
            ],
            how_to_fix=[
                "Pass a non-empty list of Edge objects.",
                "Ensure consecutive edges share matching endpoints.",
                "Inspect the edge order if the wire should form a closed loop.",
            ],
            error=e,
        )


def make_wire_from_sketch_rwire(
    sketch: Sketch,
    profile: int | str = 0,
    *,
    require_fully_constrained: bool = False,
    strict: bool = True,
    tolerance: float = 1e-7,
    max_iterations: int = 80,
) -> Wire:
    """Promote a sketch profile to a concrete wire, solving internally."""
    try:
        if not isinstance(sketch, Sketch):
            raise ValueError("Input must be a Sketch")
        wire, solve_result, profile_payload = _promote_sketch_profile(
            sketch,
            profile,
            target_kind="wire",
            require_fully_constrained=require_fully_constrained,
            strict=strict,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
        solve_snapshot = _sketch_solve_snapshot(solve_result)
        return cast(
            Wire,
            _finalize_derived_shape(
                cast(Wire, wire),
                op=_OP_MAKE_WIRE_FROM_SKETCH_RWIRE,
                params={
                    "profile": profile,
                    "sketch": sketch.to_dict(),
                    "require_fully_constrained": require_fully_constrained,
                    "strict": strict,
                    "tolerance": tolerance,
                    "max_iterations": max_iterations,
                    "solve_snapshot": solve_snapshot,
                    "promotion_map": _sketch_promotion_map(
                        sketch, profile, profile_payload
                    ),
                },
                input_shapes=cast(Sequence[AnyShape], [sketch]),
                tags={"derived", "wire", "sketch"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_wire_from_sketch_rwire",
            what_happened="Failed to create a wire from the sketch.",
            possible_causes=[
                "The sketch has no closed non-construction profile.",
                "The sketch constraints are conflicting or invalid.",
                "The requested profile index or id does not exist.",
            ],
            how_to_fix=[
                "Build sketch profiles only through sketch APIs and close all profile loops.",
                "Call inspect_sketch_rsketchresult(..., strict=False) to inspect diagnostics.",
            ],
            error=e,
        )


def make_face_from_sketch_rface(
    sketch: Sketch,
    profile: int | str = 0,
    *,
    require_fully_constrained: bool = False,
    strict: bool = True,
    tolerance: float = 1e-7,
    max_iterations: int = 80,
) -> Face:
    """Promote a sketch profile to a concrete face, solving internally."""
    try:
        if not isinstance(sketch, Sketch):
            raise ValueError("Input must be a Sketch")
        face, solve_result, profile_payload = _promote_sketch_profile(
            sketch,
            profile,
            target_kind="face",
            require_fully_constrained=require_fully_constrained,
            strict=strict,
            tolerance=tolerance,
            max_iterations=max_iterations,
        )
        solve_snapshot = _sketch_solve_snapshot(solve_result)
        return cast(
            Face,
            _finalize_derived_shape(
                cast(Face, face),
                op=_OP_MAKE_FACE_FROM_SKETCH_RFACE,
                params={
                    "profile": profile,
                    "sketch": sketch.to_dict(),
                    "require_fully_constrained": require_fully_constrained,
                    "strict": strict,
                    "tolerance": tolerance,
                    "max_iterations": max_iterations,
                    "solve_snapshot": solve_snapshot,
                    "promotion_map": _sketch_promotion_map(
                        sketch, profile, profile_payload
                    ),
                },
                input_shapes=cast(Sequence[AnyShape], [sketch]),
                tags={"derived", "face", "sketch"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_face_from_sketch_rface",
            what_happened="Failed to create a face from the sketch.",
            possible_causes=[
                "The sketch has no closed non-construction profile.",
                "The sketch constraints are conflicting or invalid.",
                "The requested profile index or id does not exist.",
            ],
            how_to_fix=[
                "Build a closed profile with add_line_rsketch(...) or add_circle_rsketch(...).",
                "Add constraints until the profile can solve cleanly.",
            ],
            error=e,
        )


def make_box_rsolid(
    width: ScalarLike,
    height: ScalarLike,
    depth: ScalarLike,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
) -> Solid:
    """Create a box solid."""
    try:
        width_value = evaluate_scalar(width)
        height_value = evaluate_scalar(height)
        depth_value = evaluate_scalar(depth)

        if width_value <= 0 or height_value <= 0 or depth_value <= 0:
            raise ValueError("宽度、高度和深度必须大于0")

        cs = get_current_cs()
        center_value = cast(
            Tuple[float, float, float], evaluate_value(bottom_face_center)
        )
        center_global = cs.transform_point(np.array(center_value))
        pnt = center_global - np.array([width_value / 2, height_value / 2, 0])

        solid = Solid(
            make_box_solid(
                (float(pnt[0]), float(pnt[1]), float(pnt[2])),
                width_value,
                height_value,
                depth_value,
            )
        )

        # 自动标记面
        solid.auto_tag_faces("box")
        solid._apply_tag("geom.primitive.box", propagate=False)
        solid._add_tag("box")
        solid.set_metadata(
            "geo",
            {
                "type": "box",
                "size": {"x": width_value, "y": height_value, "z": depth_value},
                "bottom_face_center": bottom_face_center,
            },
        )

        return _finalize_primitive_solid(
            solid,
            op="make_box_rsolid",
            params={
                "width": width,
                "height": height,
                "depth": depth,
                "bottom_face_center": bottom_face_center,
            },
            tags={"primitive", "solid"},
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_box_rsolid",
            what_happened="Failed to create a box solid.",
            possible_causes=[
                "Width, height, or depth is not a positive finite scalar.",
                "The bottom face center is not a valid finite 3D point.",
                "The kernel rejected the box dimensions or placement.",
            ],
            how_to_fix=[
                "Use width, height, and depth values greater than zero.",
                "Pass bottom_face_center as a finite 3D tuple.",
                "If dimensions come from expressions, inspect the evaluated numeric values.",
            ],
            error=e,
        )


def make_cylinder_rsolid(
    radius: ScalarLike,
    height: ScalarLike,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
    axis: Tuple[float, float, float] = (0, 0, 1),
) -> Solid:
    """Create a cylinder solid."""
    try:
        radius_value = evaluate_scalar(radius)
        height_value = evaluate_scalar(height)
        if radius_value <= 0 or height_value <= 0:
            raise ValueError("半径和高度必须大于0")

        cs = get_current_cs()
        center_value = cast(
            Tuple[float, float, float], evaluate_value(bottom_face_center)
        )
        axis_value = cast(Tuple[float, float, float], evaluate_value(axis))
        center_global = cs.transform_point(np.array(center_value))
        axis_global = cs.transform_vector(np.array(axis_value))

        solid = Solid(
            make_cylinder_solid(
                (
                    float(center_global[0]),
                    float(center_global[1]),
                    float(center_global[2]),
                ),
                (float(axis_global[0]), float(axis_global[1]), float(axis_global[2])),
                radius_value,
                height_value,
            )
        )

        # 自动标记面
        solid.auto_tag_faces("cylinder")
        solid._apply_tag("geom.primitive.cylinder", propagate=False)
        solid._add_tag("cylinder")
        solid.set_metadata(
            "geo",
            {
                "type": "cylinder",
                "radius": radius_value,
                "height": height_value,
                "bottom_face_center": bottom_face_center,
                "axis": axis,
            },
        )

        return _finalize_primitive_solid(
            solid,
            op="make_cylinder_rsolid",
            params={
                "radius": radius,
                "height": height,
                "bottom_face_center": bottom_face_center,
                "axis": axis,
            },
            tags={"primitive", "solid"},
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_cylinder_rsolid",
            what_happened="Failed to create a cylinder solid.",
            possible_causes=[
                "Radius or height is not a positive finite scalar.",
                "The bottom face center or axis is not a valid finite 3D vector.",
                "The axis is degenerate or rejected by the kernel.",
            ],
            how_to_fix=[
                "Use radius and height values greater than zero.",
                "Pass a valid bottom_face_center and a non-zero axis vector.",
                "If the axis is computed dynamically, inspect its evaluated numeric value.",
            ],
            error=e,
        )


def make_cone_rsolid(
    bottom_radius: ScalarLike,
    height: ScalarLike,
    top_radius: ScalarLike = 0.0,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
    axis: Tuple[float, float, float] = (0, 0, 1),
) -> Solid:
    """Create a cone or truncated cone solid."""
    try:
        bottom_radius_value = evaluate_scalar(bottom_radius)
        height_value = evaluate_scalar(height)
        top_radius_value = evaluate_scalar(top_radius)
        if bottom_radius_value <= 0 or height_value <= 0:
            raise ValueError("底面半径和高度必须大于0")

        cs = get_current_cs()
        center_value = cast(
            Tuple[float, float, float], evaluate_value(bottom_face_center)
        )
        axis_value = cast(Tuple[float, float, float], evaluate_value(axis))
        center_global = cs.transform_point(np.array(center_value))
        axis_global = cs.transform_vector(np.array(axis_value))

        solid = Solid(
            make_cone_solid(
                (
                    float(center_global[0]),
                    float(center_global[1]),
                    float(center_global[2]),
                ),
                (float(axis_global[0]), float(axis_global[1]), float(axis_global[2])),
                bottom_radius_value,
                top_radius_value,
                height_value,
            )
        )

        # 自动标记面
        solid._apply_tag("geom.primitive.cone", propagate=False)
        solid._add_tag("cone")
        solid.set_metadata(
            "geo",
            {
                "type": "cone",
                "bottom_radius": bottom_radius_value,
                "top_radius": top_radius_value,
                "height": height_value,
                "bottom_face_center": bottom_face_center,
                "axis": axis,
            },
        )

        return _finalize_primitive_solid(
            solid,
            op="make_cone_rsolid",
            params={
                "bottom_radius": bottom_radius,
                "top_radius": top_radius,
                "height": height,
                "bottom_face_center": bottom_face_center,
                "axis": axis,
            },
            tags={"primitive", "solid"},
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_cone_rsolid",
            what_happened="Failed to create a cone or truncated cone solid.",
            possible_causes=[
                "Bottom radius or height is not a positive finite scalar.",
                "The bottom face center or axis is not a valid finite 3D vector.",
                "The kernel rejected the cone dimensions or orientation.",
            ],
            how_to_fix=[
                "Use a positive bottom radius and a positive height.",
                "Pass a valid center point and non-zero axis vector.",
                "If top_radius is used, make sure it is a finite scalar.",
            ],
            error=e,
        )


def make_sphere_rsolid(
    radius: ScalarLike, center: Tuple[float, float, float] = (0, 0, 0)
) -> Solid:
    """Create a sphere solid."""
    try:
        radius_value = evaluate_scalar(radius)
        if radius_value <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        center_value = cast(Tuple[float, float, float], evaluate_value(center))
        center_global = cs.transform_point(np.array(center_value))

        solid = Solid(
            make_sphere_solid(
                (
                    float(center_global[0]),
                    float(center_global[1]),
                    float(center_global[2]),
                ),
                radius_value,
            )
        )

        # 自动标记面
        solid.auto_tag_faces("sphere")
        solid._apply_tag("geom.primitive.sphere", propagate=False)
        solid._add_tag("sphere")
        solid.set_metadata(
            "geo",
            {
                "type": "sphere",
                "radius": radius_value,
                "center": center,
            },
        )

        return _finalize_primitive_solid(
            solid,
            op="make_sphere_rsolid",
            params={
                "radius": radius,
                "center": center,
            },
            tags={"primitive", "solid"},
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_sphere_rsolid",
            what_happened="Failed to create a sphere solid.",
            possible_causes=[
                "The radius is not a positive finite scalar.",
                "The center is not a valid finite 3D point.",
                "The kernel rejected the sphere definition.",
            ],
            how_to_fix=[
                "Use a radius greater than zero.",
                "Pass center as a finite 3D tuple.",
                "If the center is expression-driven, inspect the evaluated coordinates.",
            ],
            error=e,
        )


def make_three_point_arc_redge(
    start: Tuple[float, float, float],
    middle: Tuple[float, float, float],
    end: Tuple[float, float, float],
) -> Edge:
    """Create an arc edge from three points."""
    try:
        cs = get_current_cs()
        start_value = cast(Tuple[float, float, float], evaluate_value(start))
        middle_value = cast(Tuple[float, float, float], evaluate_value(middle))
        end_value = cast(Tuple[float, float, float], evaluate_value(end))
        start_global = cs.transform_point(np.array(start_value))
        middle_global = cs.transform_point(np.array(middle_value))
        end_global = cs.transform_point(np.array(end_value))

        edge_shape = make_arc_three_point_edge(start_global, middle_global, end_global)
        return cast(
            Edge,
            _finalize_primitive_shape(
                Edge(edge_shape),
                op=_OP_MAKE_THREE_POINT_ARC_REDGE,
                params={"start": start, "middle": middle, "end": end},
                tags={"primitive", "edge"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_three_point_arc_redge",
            what_happened="Failed to create a three-point arc edge.",
            possible_causes=[
                "One or more points are invalid.",
                "The three points are collinear or nearly collinear.",
                "The kernel rejected the derived arc geometry.",
            ],
            how_to_fix=[
                "Pass three finite 3D points.",
                "Make sure the three points do not lie on the same straight line.",
                "If points are computed dynamically, log them before retrying.",
            ],
            error=e,
        )


def make_three_point_arc_rwire(
    start: Tuple[float, float, float],
    middle: Tuple[float, float, float],
    end: Tuple[float, float, float],
) -> Wire:
    """Create a wire containing an arc defined by three points."""
    try:
        if get_active_session() is not None:
            edge = make_three_point_arc_redge(start, middle, end)
            return make_wire_from_edges_rwire([edge])

        with suspend_graph_recording():
            edge = make_three_point_arc_redge(start, middle, end)
        wire_shape = make_wire_from_edges_ocp([edge.wrapped])
        return cast(
            Wire,
            _finalize_primitive_shape(
                Wire(wire_shape),
                op="make_three_point_arc_wire",
                params={"start": start, "middle": middle, "end": end},
                tags={"primitive", "wire"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_three_point_arc_rwire",
            what_happened="Failed to create a wire from the three-point arc.",
            possible_causes=[
                "The arc edge could not be created.",
                "The wire assembly step rejected the generated edge.",
            ],
            how_to_fix=[
                "Verify the three arc points first.",
                "If the edge is valid but the wire still fails, inspect the generated arc geometry.",
            ],
            error=e,
        )


def make_angle_arc_redge(
    center: Tuple[float, float, float],
    radius: ScalarLike,
    start_angle: ScalarLike,
    end_angle: ScalarLike,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Edge:
    """Create an arc edge from a center, radius, and angle range."""
    try:
        radius_value = evaluate_scalar(radius)
        start_angle_value = evaluate_scalar(start_angle)
        end_angle_value = evaluate_scalar(end_angle)
        if radius_value <= 0:
            raise ValueError("半径必须大于0")
        if start_angle_value == end_angle_value:
            raise ValueError("起始角度和结束角度不能相同")

        cs = get_current_cs()
        center_value = cast(Tuple[float, float, float], evaluate_value(center))
        normal_value = cast(Tuple[float, float, float], evaluate_value(normal))
        center_global = cs.transform_point(np.array(center_value))
        normal_global = cs.transform_point(np.array(normal_value)) - cs.origin

        # 标准化法向量
        normal_vec = normal_global / np.linalg.norm(normal_global)

        # 创建本地坐标系
        # 如果法向量接近Z轴，使用X轴作为参考
        if abs(normal_vec[2]) > 0.9:
            ref_vec = np.array([1.0, 0.0, 0.0])
        else:
            ref_vec = np.array([0.0, 0.0, 1.0])

        # 计算本地坐标系的X和Y轴
        local_x = np.cross(normal_vec, ref_vec)
        local_x = local_x / np.linalg.norm(local_x)
        local_y = np.cross(normal_vec, local_x)
        local_y = local_y / np.linalg.norm(local_y)

        # 在本地坐标系中计算起始、结束和中间点
        start_local = np.array(
            [
                radius_value * np.cos(start_angle_value),
                radius_value * np.sin(start_angle_value),
                0,
            ]
        )
        end_local = np.array(
            [
                radius_value * np.cos(end_angle_value),
                radius_value * np.sin(end_angle_value),
                0,
            ]
        )
        mid_angle = (start_angle_value + end_angle_value) / 2
        mid_local = np.array(
            [radius_value * np.cos(mid_angle), radius_value * np.sin(mid_angle), 0]
        )

        # 转换到全局坐标系
        start_global = (
            center_global + start_local[0] * local_x + start_local[1] * local_y
        )
        end_global = center_global + end_local[0] * local_x + end_local[1] * local_y
        mid_global = center_global + mid_local[0] * local_x + mid_local[1] * local_y

        edge_shape = make_arc_angle_edge(
            center_global,
            radius_value,
            start_angle_value,
            end_angle_value,
            normal_global,
        )
        return cast(
            Edge,
            _finalize_primitive_shape(
                Edge(edge_shape),
                op=_OP_MAKE_ANGLE_ARC_REDGE,
                params={
                    "center": center,
                    "radius": radius,
                    "start_angle": start_angle,
                    "end_angle": end_angle,
                    "normal": normal,
                },
                tags={"primitive", "edge"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_angle_arc_redge",
            what_happened="Failed to create an angle-defined arc edge.",
            possible_causes=[
                "The radius is not positive.",
                "The start and end angles collapse to the same value.",
                "The center or normal is invalid, or the kernel rejected the arc.",
            ],
            how_to_fix=[
                "Use a positive radius.",
                "Make sure start_angle and end_angle are different.",
                "Pass a valid finite center and a non-zero normal vector.",
            ],
            error=e,
        )


def make_angle_arc_rwire(
    center: Tuple[float, float, float],
    radius: float,
    start_angle: float,
    end_angle: float,
    normal: Tuple[float, float, float] = (0, 0, 1),
) -> Wire:
    """Create a wire containing an arc defined by a center, radius, and angle range."""

    try:
        if get_active_session() is not None:
            edge = make_angle_arc_redge(center, radius, start_angle, end_angle, normal)
            return make_wire_from_edges_rwire([edge])

        with suspend_graph_recording():
            edge = make_angle_arc_redge(center, radius, start_angle, end_angle, normal)
        wire_shape = make_wire_from_edges_ocp([edge.wrapped])
        return cast(
            Wire,
            _finalize_primitive_shape(
                Wire(wire_shape),
                op="make_angle_arc_wire",
                params={
                    "center": center,
                    "radius": radius,
                    "start_angle": start_angle,
                    "end_angle": end_angle,
                    "normal": normal,
                },
                tags={"primitive", "wire"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_angle_arc_rwire",
            what_happened="Failed to create a wire from the angle-defined arc.",
            possible_causes=[
                "The underlying arc edge could not be created.",
                "The wire assembly step rejected the generated edge.",
            ],
            how_to_fix=[
                "Check the center, radius, angle range, and normal.",
                "Retry after validating the arc edge input values.",
            ],
            error=e,
        )


def _normalize_bspline_control_points(
    control_points: Sequence[Sequence[ScalarLike]],
) -> Tuple[Tuple[float, float, float], ...]:
    points = list(control_points)
    if not points:
        raise ValueError("control_points must contain at least one point")
    normalized: List[Tuple[float, float, float]] = []
    for index, point in enumerate(points):
        value = cast(Sequence[float], evaluate_value(point))
        if len(value) == 2:
            coords = (float(value[0]), float(value[1]), 0.0)
        elif len(value) == 3:
            coords = (float(value[0]), float(value[1]), float(value[2]))
        else:
            raise ValueError(f"control point {index} must be 2D or 3D")
        if not all(math.isfinite(component) for component in coords):
            raise ValueError(f"control point {index} contains a non-finite coordinate")
        normalized.append(coords)
    return tuple(normalized)


def _collapse_knot_vector(
    knots: Sequence[ScalarLike],
) -> Tuple[Tuple[float, ...], Tuple[int, ...]]:
    values = [float(evaluate_scalar(knot)) for knot in knots]
    if not values:
        raise ValueError("knots must not be empty")
    if any(not math.isfinite(value) for value in values):
        raise ValueError("knots must contain only finite values")
    for previous, current in zip(values, values[1:]):
        if current < previous:
            raise ValueError(
                "knots must be non-decreasing when passed as a full knot vector"
            )
    unique: List[float] = []
    multiplicities: List[int] = []
    for value in values:
        if unique and abs(value - unique[-1]) <= 1e-12:
            multiplicities[-1] += 1
        else:
            unique.append(value)
            multiplicities.append(1)
    return tuple(unique), tuple(multiplicities)


def _default_bspline_knots(
    control_count: int, degree: int, periodic: bool
) -> Tuple[Tuple[float, ...], Tuple[int, ...]]:
    if periodic:
        knot_count = control_count + 1
        return (
            tuple(index / (knot_count - 1) for index in range(knot_count)),
            tuple(1 for _ in range(knot_count)),
        )
    knot_count = control_count - degree + 1
    if knot_count < 2:
        raise ValueError("control point count must be at least degree + 1")
    knots = tuple(index / (knot_count - 1) for index in range(knot_count))
    multiplicities = [degree + 1]
    multiplicities.extend(1 for _ in range(max(0, knot_count - 2)))
    multiplicities.append(degree + 1)
    return knots, tuple(multiplicities)


def _normalize_bspline_knots(
    *,
    control_count: int,
    degree: int,
    periodic: bool,
    knots: Optional[Sequence[ScalarLike]],
    multiplicities: Optional[Sequence[int]],
) -> Tuple[Tuple[float, ...], Tuple[int, ...]]:
    if knots is None:
        if multiplicities is not None:
            raise ValueError("multiplicities require explicit knots")
        unique_knots, mults = _default_bspline_knots(control_count, degree, periodic)
    elif multiplicities is None:
        unique_knots, mults = _collapse_knot_vector(knots)
    else:
        unique_knots = tuple(float(evaluate_scalar(knot)) for knot in knots)
        mults = tuple(int(value) for value in multiplicities)

    if len(unique_knots) != len(mults):
        raise ValueError("knots and multiplicities must have the same length")
    if len(unique_knots) < 2:
        raise ValueError("at least two unique knots are required")
    if any(not math.isfinite(knot) for knot in unique_knots):
        raise ValueError("knots must contain only finite values")
    for previous, current in zip(unique_knots, unique_knots[1:]):
        if current <= previous:
            raise ValueError("unique knots must be strictly increasing")
    if any(multiplicity <= 0 for multiplicity in mults):
        raise ValueError("multiplicities must be positive integers")
    if any(multiplicity > degree + 1 for multiplicity in mults):
        raise ValueError("multiplicities must not exceed degree + 1")

    expected_sum = control_count + (1 if periodic else degree + 1)
    actual_sum = sum(mults)
    if actual_sum != expected_sum:
        raise ValueError(
            "sum(multiplicities) must equal "
            f"{expected_sum} for this {'periodic' if periodic else 'non-periodic'} B-spline"
        )
    return tuple(unique_knots), tuple(mults)


def _normalize_bspline_weights(
    weights: Optional[Sequence[ScalarLike]], control_count: int
) -> Optional[Tuple[float, ...]]:
    if weights is None:
        return None
    values = tuple(float(evaluate_scalar(weight)) for weight in weights)
    if len(values) != control_count:
        raise ValueError("weights must contain exactly one value per control point")
    if any(not math.isfinite(value) or value <= 0.0 for value in values):
        raise ValueError("weights must be finite positive values")
    return values


def make_spline_redge(
    *,
    control_points: Sequence[Sequence[ScalarLike]],
    degree: int = 3,
    knots: Optional[Sequence[ScalarLike]] = None,
    multiplicities: Optional[Sequence[int]] = None,
    weights: Optional[Sequence[ScalarLike]] = None,
    periodic: bool = False,
) -> Edge:
    """Create an exact B-spline edge from named control-point parameters.

    Pass sampled curve points through `fit_cubic_bspline_control_points(...)` first,
    then pass the result fields explicitly as `control_points=...`, `knots=...`,
    and `multiplicities=...`. `control_points` are poles, not interpolation
    points; the curve generally does not pass through interior poles.
    """
    try:
        if isinstance(degree, bool) or int(degree) != degree:
            raise ValueError("degree must be an integer")
        degree_value = int(degree)
        if degree_value < 1:
            raise ValueError("degree must be at least 1")
        if degree_value > 25:
            raise ValueError("degree must be 25 or lower")
        periodic_value = bool(periodic)

        local_control_points = _normalize_bspline_control_points(control_points)
        if len(local_control_points) < degree_value + 1:
            raise ValueError("control point count must be at least degree + 1")
        resolved_knots, resolved_multiplicities = _normalize_bspline_knots(
            control_count=len(local_control_points),
            degree=degree_value,
            periodic=periodic_value,
            knots=knots,
            multiplicities=multiplicities,
        )
        resolved_weights = _normalize_bspline_weights(
            weights, len(local_control_points)
        )

        cs = get_current_cs()
        global_control_points = tuple(
            tuple(float(component) for component in cs.transform_point(np.array(point)))
            for point in local_control_points
        )
        edge_shape = make_bspline_edge(
            control_points=global_control_points,
            degree=degree_value,
            knots=resolved_knots,
            multiplicities=resolved_multiplicities,
            weights=resolved_weights,
            periodic=periodic_value,
        )
        edge = Edge(edge_shape)
        edge.set_metadata(
            "geo",
            {
                "type": "bspline",
                "degree": degree_value,
                "control_points": [list(point) for point in global_control_points],
                "knots": list(resolved_knots),
                "multiplicities": list(resolved_multiplicities),
                "weights": (
                    list(resolved_weights) if resolved_weights is not None else None
                ),
                "periodic": periodic_value,
            },
        )

        return cast(
            Edge,
            _finalize_primitive_shape(
                edge,
                op=_OP_MAKE_SPLINE_REDGE,
                params={
                    "control_points": control_points,
                    "degree": degree_value,
                    "knots": resolved_knots,
                    "multiplicities": resolved_multiplicities,
                    "weights": weights,
                    "periodic": periodic_value,
                },
                tags={"primitive", "edge"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_spline_redge",
            what_happened="Failed to create a spline edge.",
            possible_causes=[
                "The exact B-spline definition is inconsistent.",
                "Control points, knots, multiplicities, or weights are invalid.",
                "A sampled-point list was passed directly instead of fitted control points.",
            ],
            how_to_fix=[
                "Pass keyword arguments such as control_points=..., degree=3, knots=..., multiplicities=....",
                "Use fit_cubic_bspline_control_points(sample_points) for sampled curves, then pass its result fields explicitly.",
                "Ensure sum(multiplicities) matches the exact B-spline degree/control-count rule.",
            ],
            error=e,
        )


def make_spline_rwire(
    *,
    control_points: Sequence[Sequence[ScalarLike]],
    degree: int = 3,
    knots: Optional[Sequence[ScalarLike]] = None,
    multiplicities: Optional[Sequence[int]] = None,
    weights: Optional[Sequence[ScalarLike]] = None,
    periodic: bool = False,
) -> Wire:
    """Create a wire containing one exact B-spline edge."""
    try:
        edge_kwargs = {
            "control_points": control_points,
            "degree": degree,
            "knots": knots,
            "multiplicities": multiplicities,
            "weights": weights,
            "periodic": periodic,
        }
        if get_active_session() is not None:
            edge = make_spline_redge(**edge_kwargs)
            return make_wire_from_edges_rwire([edge])

        with suspend_graph_recording():
            edge = make_spline_redge(**edge_kwargs)
        wire_shape = make_wire_from_edges_ocp([edge.wrapped])
        rv = Wire(wire_shape)
        return cast(
            Wire,
            _finalize_primitive_shape(
                rv,
                op="make_spline_wire",
                params=edge_kwargs,
                tags={"primitive", "wire"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_spline_rwire",
            what_happened="Failed to create a spline wire.",
            possible_causes=[
                "The spline edge could not be created.",
                "The exact B-spline definition is inconsistent.",
                "The kernel rejected the resulting wire geometry.",
            ],
            how_to_fix=[
                "Validate the B-spline control points, degree, knots, multiplicities, and weights first.",
                "For sampled curves, call fit_cubic_bspline_control_points(...) and pass the result fields explicitly.",
                "Retry after inspecting the evaluated spline inputs.",
            ],
            error=e,
        )


def make_polyline_rwire(
    points: List[Tuple[ScalarLike, ScalarLike, ScalarLike]], closed: bool = False
) -> Wire:
    """Create a polyline wire from a point list."""
    try:
        if len(points) < 2:
            raise ValueError("至少需要2个点")

        if get_active_session() is not None:
            edges = [
                make_line_redge(points[idx], points[idx + 1])
                for idx in range(len(points) - 1)
            ]
            if closed and len(points) > 2:
                edges.append(make_line_redge(points[-1], points[0]))
            return make_wire_from_edges_rwire(edges)

        cs = get_current_cs()

        # 转换所有点到全局坐标系
        global_points = []
        for point in points:
            point_value = cast(Tuple[float, float, float], evaluate_value(point))
            global_point = cs.transform_point(np.array(point_value))
            global_points.append(tuple(float(v) for v in global_point))

        wire_shape = make_polyline_wire(
            [
                (float(point[0]), float(point[1]), float(point[2]))
                for point in global_points
            ],
            closed=closed,
        )
        return cast(
            Wire,
            _finalize_primitive_shape(
                Wire(wire_shape),
                op="make_polyline_wire",
                params={"points": points, "closed": closed},
                tags={"primitive", "wire"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_polyline_rwire",
            what_happened="Failed to create a polyline wire.",
            possible_causes=[
                "Fewer than two points were provided.",
                "One or more points are invalid or non-finite.",
                "The kernel rejected the resulting polyline geometry.",
            ],
            how_to_fix=[
                "Pass at least two finite 3D points.",
                "If closed=True, ensure the sequence describes a valid loop.",
                "Inspect the evaluated points before retrying.",
            ],
            error=e,
        )


def make_helix_redge(
    pitch: ScalarLike,
    height: ScalarLike,
    radius: ScalarLike,
    center: Tuple[float, float, float] = (0, 0, 0),
    dir: Tuple[float, float, float] = (0, 0, 1),
) -> Edge:
    """Create a helix edge."""
    try:
        pitch_value = evaluate_scalar(pitch)
        height_value = evaluate_scalar(height)
        radius_value = evaluate_scalar(radius)
        if pitch_value <= 0:
            raise ValueError("螺距必须大于0")
        if height_value <= 0:
            raise ValueError("高度必须大于0")
        if radius_value <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        center_value = cast(Tuple[float, float, float], evaluate_value(center))
        dir_value = cast(Tuple[float, float, float], evaluate_value(dir))
        global_center = cs.transform_point(np.array(center_value))
        global_dir = cs.transform_point(np.array(dir_value)) - cs.origin

        wire_shape = make_helix_wire(
            pitch_value, height_value, radius_value, global_center, global_dir
        )
        wire = Wire(wire_shape)
        edges = wire.get_edges()
        if not edges:
            raise ValueError("无法从螺旋线中提取边")
        helix_edge = edges[0]
        return cast(
            Edge,
            _finalize_primitive_shape(
                helix_edge,
                op=_OP_MAKE_HELIX_REDGE,
                params={
                    "pitch": pitch,
                    "height": height,
                    "radius": radius,
                    "center": center,
                    "dir": dir,
                },
                tags={"primitive", "edge"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_helix_redge",
            what_happened="Failed to create a helix edge.",
            possible_causes=[
                "Pitch, height, or radius is not positive.",
                "The center or direction vector is invalid.",
                "The kernel rejected the helix definition.",
            ],
            how_to_fix=[
                "Use positive pitch, height, and radius values.",
                "Pass a valid center and a non-zero direction vector.",
                "Inspect the evaluated helix parameters before retrying.",
            ],
            error=e,
        )


def make_helix_rwire(
    pitch: float,
    height: float,
    radius: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    dir: Tuple[float, float, float] = (0, 0, 1),
) -> Wire:
    """Create a helix wire."""
    try:
        if get_active_session() is not None:
            edge = make_helix_redge(pitch, height, radius, center=center, dir=dir)
            return make_wire_from_edges_rwire([edge])

        cs = get_current_cs()
        global_center = cs.transform_point(np.array(center))
        global_dir = cs.transform_point(np.array(dir)) - cs.origin

        wire_shape = make_helix_wire(pitch, height, radius, global_center, global_dir)
        return cast(
            Wire,
            _finalize_primitive_shape(
                Wire(wire_shape),
                op="make_helix_wire",
                params={
                    "pitch": pitch,
                    "height": height,
                    "radius": radius,
                    "center": center,
                    "dir": dir,
                },
                tags={"primitive", "wire"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_helix_rwire",
            what_happened="Failed to create a helix wire.",
            possible_causes=[
                "The helix parameters are invalid.",
                "The direction vector is zero or malformed.",
                "The kernel rejected the wire geometry.",
            ],
            how_to_fix=[
                "Use positive pitch, height, and radius values.",
                "Pass a valid center and a non-zero direction vector.",
                "Retry after logging the evaluated helix parameters.",
            ],
            error=e,
        )


# =============================================================================
# 变换操作函数
# =============================================================================


def translate_shape(shape: AnyShape, vector: Tuple[float, float, float]) -> AnyShape:
    """Translate a shape by an offset vector."""
    try:
        if isinstance(shape, Solid):
            vector_value = cast(Tuple[float, float, float], evaluate_value(vector))
            tracked = tracked_translate(shape, vector_value)
            translated = cast(Solid, tracked.shape)
            translated._metadata = shape._metadata.copy()
            _attach_lineage_from_source(
                shape,
                translated,
                derivation="continuation",
                op=_OP_MAKE_TRANSLATE_RSHAPE,
            )
            return _finalize_tracked_solid(
                translated,
                op=_OP_MAKE_TRANSLATE_RSHAPE,
                params={"vector": vector},
                source_solid=shape,
                delta=tracked.delta,
                delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
                input_shapes=[shape],
            )

        cs = get_current_cs()
        vector_value = cast(Tuple[float, float, float], evaluate_value(vector))
        global_vector = cs.transform_point(np.array(vector_value)) - cs.origin
        new_shape = translate_shape_ocp(
            shape,
            (
                float(global_vector[0]),
                float(global_vector[1]),
                float(global_vector[2]),
            ),
        )

        new_shape._metadata = shape._metadata.copy()
        _copy_runtime_state(shape, new_shape)
        _attach_lineage_from_source(
            shape,
            new_shape,
            derivation="continuation",
            op=_OP_MAKE_TRANSLATE_RSHAPE,
        )
        record_operation_if_active(
            op=_OP_MAKE_TRANSLATE_RSHAPE,
            params={"vector": vector},
            outputs=new_shape,
            input_shapes=[shape],
            context=_current_context_metadata(),
        )

        return new_shape
    except Exception as e:
        _wrap_public_api_error(
            operation="translate_shape",
            what_happened="Failed to translate the shape.",
            possible_causes=[
                "The shape is invalid or has been corrupted by an earlier operation.",
                "The translation vector is not a valid finite 3D vector.",
                "The kernel rejected the transform.",
            ],
            how_to_fix=[
                "Pass a valid SimpleCAD shape object.",
                "Pass vector as a finite 3-element tuple or expression-backed vector.",
                "Inspect the shape and vector values before retrying.",
            ],
            error=e,
        )


def rotate_shape(
    shape: AnyShape,
    angle: ScalarLike,
    axis: Tuple[float, float, float] = (0, 0, 1),
    origin: Tuple[float, float, float] = (0, 0, 0),
) -> AnyShape:
    """Rotate a shape around an axis."""
    angle_value = evaluate_scalar(angle)
    if angle_value == 0:
        return shape
    else:
        try:
            if isinstance(shape, Solid):
                axis_value = cast(Tuple[float, float, float], evaluate_value(axis))
                origin_value = cast(Tuple[float, float, float], evaluate_value(origin))
                tracked = tracked_rotate(
                    shape, angle_value, axis=axis_value, origin=origin_value
                )
                rotated = cast(Solid, tracked.shape)
                rotated._metadata = shape._metadata.copy()
                _attach_lineage_from_source(
                    shape,
                    rotated,
                    derivation="continuation",
                    op=_OP_MAKE_ROTATE_RSHAPE,
                )
                return _finalize_tracked_solid(
                    rotated,
                    op=_OP_MAKE_ROTATE_RSHAPE,
                    params={"angle": angle, "axis": axis, "origin": origin},
                    source_solid=shape,
                    delta=tracked.delta,
                    delta_entries=cast(
                        Dict[str, Dict[str, object]], tracked.delta_entries
                    ),
                    input_shapes=[shape],
                )

            cs = get_current_cs()
            axis_value = cast(Tuple[float, float, float], evaluate_value(axis))
            origin_value = cast(Tuple[float, float, float], evaluate_value(origin))
            global_axis = cs.transform_point(np.array(axis_value)) - cs.origin
            global_origin = cs.transform_point(np.array(origin_value))
            new_shape = rotate_shape_ocp(
                shape,
                angle_value,
                (float(global_axis[0]), float(global_axis[1]), float(global_axis[2])),
                (
                    float(global_origin[0]),
                    float(global_origin[1]),
                    float(global_origin[2]),
                ),
            )

            new_shape._metadata = shape._metadata.copy()
            _copy_runtime_state(shape, new_shape)
            _attach_lineage_from_source(
                shape,
                new_shape,
                derivation="continuation",
                op=_OP_MAKE_ROTATE_RSHAPE,
            )
            record_operation_if_active(
                op=_OP_MAKE_ROTATE_RSHAPE,
                params={"angle": angle, "axis": axis, "origin": origin},
                outputs=new_shape,
                input_shapes=[shape],
                context=_current_context_metadata(),
            )

            return new_shape
        except Exception as e:
            _wrap_public_api_error(
                operation="rotate_shape",
                what_happened="Failed to rotate the shape.",
                possible_causes=[
                    "The shape is invalid.",
                    "The rotation angle is invalid or non-finite.",
                    "The axis or origin is not a valid finite 3D vector.",
                ],
                how_to_fix=[
                    "Pass a valid shape and a finite rotation angle.",
                    "Use a non-zero axis vector and a valid origin point.",
                    "Log the evaluated angle, axis, and origin before retrying.",
                ],
                error=e,
            )


# =============================================================================
# 3D操作函数
# =============================================================================


def extrude_rsolid(
    profile: Union[Wire, Face],
    direction: Tuple[float, float, float],
    distance: ScalarLike,
    *,
    output_tags: Optional[Mapping[str, str]] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid:
    """Create a solid by extruding a profile, with optional role-based tags."""
    try:
        assignments = _normalize_operation_output_tags(
            _OP_MAKE_EXTRUDE_RSOLID,
            output_tags,
            (
                ("extrusion.start", start_face_tag),
                ("extrusion.end", end_face_tag),
                ("extrusion.side", side_faces_tag),
            ),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        distance_value = evaluate_scalar(distance)
        if distance_value <= 0:
            raise ValueError("拉伸距离必须大于0")

        cs = get_current_cs()
        direction_value = cast(Tuple[float, float, float], evaluate_value(direction))
        global_direction = cs.transform_point(np.array(direction_value)) - cs.origin

        direction_norm = float(np.linalg.norm(global_direction))
        if direction_norm <= 1e-15:
            raise ValueError("拉伸方向不能是零向量")
        direction_vec = tuple(
            (global_direction / direction_norm * distance_value).tolist()
        )

        if isinstance(profile, Wire):
            # 如果是线，先转换为面
            if profile.is_closed():
                face = Face(make_face_from_wire_ocp(profile.wrapped))
            else:
                raise ValueError(
                    "如果传入线框作为拉伸对象，那么线框必须是闭合的, 而你的线框没有闭合，请检查构成线框的点是否正确"
                )
        elif isinstance(profile, Face):
            face = profile
        else:
            raise ValueError("只能拉伸线或面")  # type: ignore[unreachable]

        tracked = tracked_extrude(
            face,
            (
                float(global_direction[0]),
                float(global_direction[1]),
                float(global_direction[2]),
            ),
            distance_value,
        )
        solid = cast(Solid, tracked.shape)

        solid._apply_tag("solid.extrusion", propagate=False)
        solid._metadata = profile._metadata.copy()

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            solid,
            op=_OP_MAKE_EXTRUDE_RSOLID,
            params={
                "direction": direction,
                "distance": distance,
            },
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[profile],
        )
        return _apply_operation_output_tags(
            finalized,
            op=_OP_MAKE_EXTRUDE_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="extrude_rsolid",
            what_happened="Failed to extrude the profile into a solid.",
            possible_causes=[
                "The distance is not a positive finite scalar.",
                "The direction vector is invalid.",
                "A wire profile was provided but it is not closed.",
                "The kernel rejected the profile or the extrusion direction.",
            ],
            how_to_fix=[
                "Use a distance greater than zero.",
                "Pass a valid finite direction vector.",
                "If you extrude a wire, make sure the wire is closed or convert it to a face first.",
                "Inspect the evaluated profile and direction before retrying.",
            ],
            error=e,
        )


def revolve_rsolid(
    profile: Union[Wire, Face],
    axis: Tuple[float, float, float] = (0, 0, 1),
    angle: ScalarLike = 360,
    origin: Tuple[float, float, float] = (0, 0, 0),
    *,
    output_tags: Optional[Mapping[str, str]] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid:
    """Create a revolved solid, with optional kernel-role-based tags."""
    try:
        assignments = _normalize_operation_output_tags(
            _OP_MAKE_REVOLVE_RSOLID,
            output_tags,
            (
                ("revolution.start", start_face_tag),
                ("revolution.end", end_face_tag),
                ("revolution.side", side_faces_tag),
            ),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        angle_value = evaluate_scalar(angle)
        if angle_value <= 0:
            raise ValueError("旋转角度必须大于0")

        cs = get_current_cs()
        axis_value = cast(Tuple[float, float, float], evaluate_value(axis))
        origin_value = cast(Tuple[float, float, float], evaluate_value(origin))
        global_axis = cs.transform_point(np.array(axis_value)) - cs.origin
        global_origin = cs.transform_point(np.array(origin_value))

        # 获取轮廓对应的面
        if isinstance(profile, Wire):
            # 如果是线，先转换为面
            if profile.is_closed():
                face = Face(make_face_from_wire_ocp(profile.wrapped))
            else:
                raise ValueError("旋转的线必须是闭合的")
        elif isinstance(profile, Face):
            face = profile
        else:
            raise ValueError("只能旋转线或面")

        tracked = tracked_revolve(
            face,
            (
                float(global_axis[0]),
                float(global_axis[1]),
                float(global_axis[2]),
            ),
            (
                float(global_origin[0]),
                float(global_origin[1]),
                float(global_origin[2]),
            ),
            angle_value,
        )
        solid = cast(Solid, tracked.shape)

        solid._metadata = profile._metadata.copy()

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            solid,
            op=_OP_MAKE_REVOLVE_RSOLID,
            params={
                "axis": axis,
                "angle": angle,
                "origin": origin,
            },
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[profile],
        )
        return _apply_operation_output_tags(
            finalized,
            op=_OP_MAKE_REVOLVE_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="revolve_rsolid",
            what_happened="Failed to revolve the profile into a solid.",
            possible_causes=[
                "The angle is not a positive finite scalar.",
                "The axis or origin is invalid.",
                "A wire profile was provided but it is not closed.",
                "The kernel rejected the revolve definition.",
            ],
            how_to_fix=[
                "Use an angle greater than zero.",
                "Pass a valid non-zero axis vector and a valid origin point.",
                "If you revolve a wire, ensure it is closed or convert it to a face first.",
                "Inspect the evaluated axis, origin, and profile before retrying.",
            ],
            error=e,
        )


# =============================================================================
# 标签和选择函数
# =============================================================================


def _semantic_view_target(view: AnyShape, target: AnyShape) -> AnyShape:
    candidates = [
        wrapper
        for entity in view._topology_cache.entities()
        if entity.kind == target._entity.kind
        for wrapper in entity.wrappers
        if isinstance(wrapper, type(target))
    ]
    matches = []
    for candidate in candidates:
        try:
            if candidate.wrapped.IsSame(target.wrapped):
                matches.append(candidate)
        except Exception:
            continue
    unique = {candidate.topo_id: candidate for candidate in matches}
    if not unique:
        raise ValueError("tag target does not belong to the assignment scope")
    if len(unique) != 1:
        raise ValueError("tag target is ambiguous within the assignment scope")
    return next(iter(unique.values()))


def apply_tag_rselection(
    scope: AnyShape,
    targets: Union[ShapeSelector, Sequence[AnyShape]],
    tag: str,
    topology_propagation: str | TopologyPropagation = TopologyPropagation.LOCAL,
    lineage_policy: str | LineagePolicy = LineagePolicy.CONTINUATION_FRAGMENT,
) -> AnyShape:
    """Return a semantic shape view with a canonical tag assignment."""

    try:
        return _apply_tag_rselection(
            scope,
            targets,
            tag,
            topology_propagation,
            lineage_policy,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="apply_tag_rselection",
            what_happened="Failed to attach the tag to the selected shapes.",
            possible_causes=[
                "The assignment scope or target selection is invalid.",
                "The tag value is empty or malformed.",
                "The selector resolved no targets or references foreign topology.",
            ],
            how_to_fix=[
                "Pass a valid scope and a non-empty ShapeSelector or shape sequence.",
                "Use a normalized tag string such as 'role.mounting_surface' or 'group.fasteners'.",
                "Ensure every explicit target belongs to the assignment scope.",
            ],
            error=e,
        )


def _apply_tag_rselection(
    scope: AnyShape,
    targets: Union[ShapeSelector, Sequence[AnyShape]],
    tag: str,
    topology_propagation: str | TopologyPropagation,
    lineage_policy: str | LineagePolicy,
    *,
    authoring_source: str = "simplecadapi.apply_tag_rselection",
    extra_evidence: Optional[Dict[str, Any]] = None,
) -> AnyShape:
    normalized_tag = normalize_tag(tag, strict=True)
    topology = TopologyPropagation(topology_propagation)
    lineage = LineagePolicy(lineage_policy)
    session = get_active_session()
    source_node = _active_graph_node_for_shape(scope)
    source_output_slot = int(scope._get_runtime("graph.output_slot", 0))
    if session is not None and source_node is None:
        raise ValueError("assignment scope is not produced by the active GraphSession")

    view = clone_semantic_shape_view(scope)
    if isinstance(targets, ShapeSelector):
        selector = targets
        if source_node is not None:
            if selector.source_node_id is None:
                selector = selector.from_source(source_node.node_id, source_output_slot)
            elif (
                selector.source_node_id != source_node.node_id
                or int(selector.source_output_slot or 0) != source_output_slot
            ):
                raise ValueError(
                    "tag selector source does not match the assignment scope"
                )
        selected = cast(List[AnyShape], selector.resolve(view))
        target = TagTarget("selection_query", selector=selector.to_dict())
    else:
        if isinstance(targets, (str, bytes)):
            raise TypeError("targets must be a ShapeSelector or shape sequence")
        target_shapes = list(targets)
        if not target_shapes:
            raise ValueError("tag assignment targets cannot be empty")
        if not all(
            isinstance(item, (Vertex, Edge, Wire, Face, Solid, Compound))
            for item in target_shapes
        ):
            raise TypeError("tag assignment targets must contain only shapes")
        selected = [
            _semantic_view_target(view, cast(AnyShape, item)) for item in target_shapes
        ]
        refs = tuple(
            ref for ref in _serialize_shape_refs(target_shapes) if isinstance(ref, dict)
        )
        if len(refs) != len(target_shapes):
            refs = tuple(
                {"kind": _shape_kind_token(item), "topo_id": item.topo_id}
                for item in target_shapes
            )
        target = TagTarget("explicit_refs", refs=refs)

    selected_by_topo_id = {item.topo_id: item for item in selected}
    if len(selected_by_topo_id) != len(selected):
        raise ValueError("tag assignment targets contain ambiguous duplicate entities")
    selected = list(selected_by_topo_id.values())
    if not selected:
        raise ValueError("tag assignment resolved no targets")

    selected_refs = _serialize_shape_refs(selected)
    if len(selected_refs) != len(selected):
        selected_refs = [
            {"kind": _shape_kind_token(item), "topo_id": item.topo_id}
            for item in selected
        ]

    assignment_node_id = (
        f"n_{uuid.uuid4().hex[:8]}" if source_node is not None else None
    )
    evidence_data = {
        "authoring_source": authoring_source,
        "selected_count": len(selected),
        "selected_refs": selected_refs,
        **dict(extra_evidence or {}),
    }
    binding = TagBinding(
        tag=normalized_tag,
        producer=TagProducer("user_operation", node_id=assignment_node_id),
        scope=TagBindingScope(
            node_id=(source_node.node_id if source_node is not None else None),
            output_slot=source_output_slot,
        ),
        target=target,
        propagation=TagPropagation(topology=topology, lineage=lineage),
        evidence=TagEvidence("query_execution", evidence_data),
        certainty=TagCertainty.ASSERTED,
        lifecycle=TagLifecycle.ASSERTION,
    )

    for selected_shape in selected:
        selected_shape._add_tag_binding(binding)

    if source_node is not None and session is not None:
        node = record_operation(
            op=_OP_APPLY_TAG_RSELECTION,
            params={"tag_binding": binding.to_dict()},
            inputs=[source_node],
            node_id=assignment_node_id,
            output_count=1,
            context=_current_context_metadata(),
        )
        attach_semantic_graph_node(
            view,
            node,
            output_slot=0,
            graph_id=session.graph.graph_id,
        )
    return view


def apply_tag(shape: AnyShape, tag: str) -> AnyShape:
    """Attach a local user tag with continuation/fragment lineage policy."""

    try:
        _ensure_source_shape_has_own_selection_node(shape)
        selector = ShapeSelector(_shape_kind_token(shape)).exactly(1)
        result = apply_tag_rselection(shape, selector, tag)
        shape._copy_tag_state_from(result)
        semantic_node = result._get_runtime("graph.node")
        session = get_active_session()
        if semantic_node is not None:
            attach_semantic_graph_node(
                shape,
                semantic_node,
                output_slot=0,
                graph_id=session.graph.graph_id if session is not None else None,
            )
        return shape
    except Exception as e:
        _wrap_public_api_error(
            operation="apply_tag",
            what_happened="Failed to attach the tag to the shape.",
            possible_causes=[
                "The shape is invalid.",
                "The tag value is empty or malformed.",
            ],
            how_to_fix=[
                "Pass a valid shape object.",
                "Use a normalized tag string such as 'role.mounting_surface' or 'group.fasteners'.",
            ],
            error=e,
        )


def list_tags(
    shape: AnyShape,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[str]:
    """Return shape tags in deterministic sorted order for one scope."""
    try:
        return shape._list_tags(normalize_tag_scope(scope))
    except Exception as e:
        _wrap_public_api_error(
            operation="list_tags",
            what_happened="Failed to list tags on the shape.",
            possible_causes=[
                "The shape is invalid.",
                "The object is not a SimpleCAD shape.",
            ],
            how_to_fix=[
                "Pass a valid Vertex, Edge, Wire, Face, or Solid object.",
            ],
            error=e,
        )


def explain_tag(
    shape: AnyShape,
    tag: str,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[Dict[str, Any]]:
    """Explain every visible binding that produces a tag token."""

    try:
        return shape._explain_tag(
            normalize_tag(tag, strict=True), normalize_tag_scope(scope)
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="explain_tag",
            what_happened="Failed to explain the tag on the shape.",
            possible_causes=[
                "The shape or tag is invalid.",
                "The requested scope requires unavailable semantic evidence.",
            ],
            how_to_fix=[
                "Pass a valid shape and normalized tag token.",
                "Request a supported scope or provide complete topology history.",
            ],
            error=e,
        )


def select_faces_by_tag(
    solid: Solid,
    tag: str,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[Face]:
    """Select faces by tag."""
    try:
        normalized = normalize_tag(tag, strict=True)
        resolved_scope = normalize_tag_scope(scope)
        faces = solid.get_faces()
        return [face for face in faces if face._has_tag(normalized, resolved_scope)]
    except Exception as e:
        _wrap_public_api_error(
            operation="select_faces_by_tag",
            what_happened="Failed to select faces by tag.",
            possible_causes=[
                "The solid is invalid.",
                "The tag string is invalid.",
            ],
            how_to_fix=[
                "Pass a valid Solid object.",
                "Use the exact face tag that was previously assigned.",
            ],
            error=e,
        )


def select_edges_by_tag(
    shape: Union[Face, Solid],
    tag: str,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[Edge]:
    """Select edges by tag."""
    try:
        normalized = normalize_tag(tag, strict=True)
        resolved_scope = normalize_tag_scope(scope)
        if isinstance(shape, Face):
            edges = shape.get_edges()
        elif isinstance(shape, Solid):
            edges = shape.get_edges()
        else:
            raise ValueError("只能从面或实体中选择边")

        return [edge for edge in edges if edge._has_tag(normalized, resolved_scope)]
    except Exception as e:
        _wrap_public_api_error(
            operation="select_edges_by_tag",
            what_happened="Failed to select edges by tag.",
            possible_causes=[
                "The input shape is neither a Face nor a Solid.",
                "The shape is invalid.",
                "The tag string is invalid.",
            ],
            how_to_fix=[
                "Pass a Face or Solid object.",
                "Use the exact edge tag that was previously assigned.",
                "If selection is empty unexpectedly, inspect the available edge tags first.",
            ],
            error=e,
        )


# =============================================================================
# 布尔运算函数
# =============================================================================


def union_rsolid(
    *solids: Union[Solid, Sequence[Solid]],
    clean: bool = True,
    glue: bool = _DEFAULT_UNION_GLUE,
    tol: Optional[float] = None,
) -> Solid:
    """Compute the boolean union and return one solid.

    Args:
        solids: One or more Solid objects or sequences of Solid. Nested sequences are
            flattened before processing.
        clean: Unify same-domain faces and remove splitter edges when possible.
        glue: Enable OCC glue mode for touching or partially overlapping inputs.
            Defaults to True for SimpleCAD's standard union behavior.
        tol: Optional fuzzy-boolean tolerance used by the OCC union kernel. When
            omitted, SimpleCAD chooses a conservative scale-aware tolerance.

    Returns:
        Solid: The merged union result.

    Usage:
        Accepts standalone `Solid` objects, lists of `Solid`, and nested sequences,
        but always returns exactly one `Solid`. If the kernel cannot produce
        exactly one solid result, the API raises a clear error instead of
        returning multiple pieces.

    Examples:
        body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
        rib = make_box_rsolid(2, 4, 4, bottom_face_center=(4, 0, 0))
        merged = union_rsolid(body, rib)
        print(merged.get_volume())
    """

    try:
        remaining = _flatten_boolean_solids(solids, "union_rsolid")

        if not remaining:
            raise ValueError("union_rsolid 至少需要一个Solid输入")

        for solid in remaining:
            if solid.wrapped.IsNull():
                raise ValueError("输入实体无效，无法进行并集运算。")

        if len(remaining) == 1 and not clean:
            return remaining[0]

        effective_tol = _resolve_union_tol(remaining, tol)
        fused_shape = fuse_shapes(
            [solid.wrapped for solid in remaining],
            glue=glue,
            tol=effective_tol,
            clean=clean,
        )
        result_shapes = solids_of(fused_shape)

        failure_reason = "并集结果中未找到有效实体。"
        if len(result_shapes) != 1:
            diagnostic = _union_separation_diagnostic(
                [Solid(result_shape) for result_shape in result_shapes], effective_tol
            )
            if diagnostic:
                failure_reason = diagnostic
        fused_solid = _require_single_boolean_solid(
            result_shapes,
            operation="union_rsolid",
            failure_reason=failure_reason,
        )

        all_metadata = {}
        for solid in remaining:
            all_metadata.update(solid._metadata)

        fused_solid._metadata = all_metadata.copy()

        tracked_union_result: Optional[TrackedBooleanResult] = None
        if len(remaining) == 2:
            try:
                tracked_union_result = tracked_union(
                    remaining[0],
                    remaining[1],
                    glue=glue,
                    tol=float(effective_tol or 0.0),
                )
            except Exception:
                tracked_union_result = None

        if tracked_union_result is not None:
            fused_solid = _finalize_tracked_solid(
                fused_solid,
                op=_OP_MAKE_UNION_RSOLID,
                params={
                    "input_count": len(remaining),
                    "clean": clean,
                    "glue": glue,
                    "tol": effective_tol,
                },
                source_solids=remaining,
                delta=tracked_union_result.delta,
                delta_entries=cast(
                    Dict[str, Dict[str, object]],
                    tracked_union_result.delta_entries,
                ),
                input_shapes=remaining,
            )
        else:
            _attach_track_summary(fused_solid, op=_OP_MAKE_UNION_RSOLID)
            record_operation_if_active(
                op=_OP_MAKE_UNION_RSOLID,
                params={
                    "input_count": len(remaining),
                    "clean": clean,
                    "glue": glue,
                    "tol": effective_tol,
                },
                outputs=fused_solid,
                input_shapes=remaining,
                context=_current_context_metadata(),
            )

        return fused_solid
    except Exception as e:
        _wrap_public_api_error(
            operation="union_rsolid",
            what_happened="Failed to compute the boolean union.",
            possible_causes=[
                "One or more inputs are not Solid objects.",
                "At least one input solid is null or invalid.",
                "The kernel could not fuse the solids into exactly one solid with the current geometry or tolerance.",
            ],
            how_to_fix=[
                "Pass only Solid objects or sequences of Solid objects.",
                "Validate each input solid before union.",
                "If the solids still remain disconnected, move them so they overlap or increase tol intentionally.",
            ],
            error=e,
        )


def cut_rsolid(
    *solids: Union[Solid, Sequence[Solid]],
    skip_non_intersecting: bool = True,
) -> Solid:
    """Compute the boolean difference of solids.

    Args:
        solids: One or more Solid objects or sequences of Solid. Nested sequences are
            flattened before processing; the first solid is the base, the rest are
            subtracted in order.
        skip_non_intersecting: When True, tools with no meaningful intersection are
            ignored for interactive convenience. Graph replay records this flag and
            should use False for strict diagnostic workflows.

    Returns:
        Solid: The cut result solid.

    Usage:
        Accepts a base solid followed by one or more tool solids, including nested
        sequences, and returns a single `Solid`.
    """
    try:
        remaining = _flatten_boolean_solids(solids, "cut_rsolid")

        if not remaining:
            raise ValueError("cut_rsolid 至少需要一个Solid输入")

        if len(remaining) == 1:
            return remaining[0]

        # 从第一个实体开始，依次减去其他实体
        result_solid = remaining[0]
        deltas: List[TopoDelta] = []
        merged_delta_entries: Dict[str, Dict[str, object]] = {}
        cut_performed = False

        for i in range(1, len(remaining)):
            candidate = remaining[i]

            s1 = result_solid.wrapped
            s2 = candidate.wrapped

            if s1.IsNull() or s2.IsNull():
                raise ValueError("输入实体无效，无法进行差集运算。")

            # 检查是否有交集
            intersection = common_shapes([s1, s2])
            intersection_solids = solids_of(intersection)
            if not intersection_solids:
                if skip_non_intersecting:
                    continue
                raise ValueError("差集工具实体与当前实体没有交集。")
            intersection_obj = Solid(intersection_solids[0])

            if intersection_obj.get_volume() < 1e-12:
                # 没有有效的交集，跳过此次切割
                if skip_non_intersecting:
                    continue
                raise ValueError("差集工具实体与当前实体交集体积过小。")

            tracked = tracked_cut(result_solid, candidate)
            if tracked.solid is None:
                raise ValueError("差集运算失败: OCC 未返回有效实体")

            new_result = tracked.solid
            new_result._metadata = result_solid._metadata.copy()
            result_solid = new_result
            deltas.append(tracked.delta)
            merged_delta_entries.update(
                cast(Dict[str, Dict[str, object]], tracked.delta_entries)
            )
            cut_performed = True

        result_solid._metadata = remaining[0]._metadata.copy()
        result_solid._apply_tag("solid.boolean.cut", propagate=False)

        merged_delta = _merge_topo_deltas(deltas)
        if cut_performed and merged_delta is not None:
            result_solid = _finalize_tracked_solid(
                result_solid,
                op=_OP_MAKE_CUT_RSOLID,
                params={
                    "tool_count": len(remaining) - 1,
                    "skip_non_intersecting": bool(skip_non_intersecting),
                },
                source_solids=remaining,
                delta=merged_delta,
                delta_entries=merged_delta_entries or None,
                input_shapes=remaining,
            )
        else:
            _attach_track_summary(result_solid, op=_OP_MAKE_CUT_RSOLID)
            record_operation_if_active(
                op=_OP_MAKE_CUT_RSOLID,
                params={
                    "tool_count": len(remaining) - 1,
                    "skip_non_intersecting": bool(skip_non_intersecting),
                },
                outputs=result_solid,
                input_shapes=remaining,
                context=_current_context_metadata(),
            )

        return result_solid
    except Exception as e:
        _wrap_public_api_error(
            operation="cut_rsolid",
            what_happened="Failed to compute the boolean cut.",
            possible_causes=[
                "One or more inputs are not Solid objects.",
                "The base solid or tool solids are invalid.",
                "The kernel could not compute a valid cut result for the current geometry.",
            ],
            how_to_fix=[
                "Pass a valid base solid followed by valid tool solids.",
                "Check whether the tool geometry actually intersects the base solid.",
                "If the cut depends on earlier union results, verify those results first.",
            ],
            error=e,
        )


def intersect_rsolid(*solids: Union[Solid, Sequence[Solid]]) -> Solid:
    """Compute the boolean intersection of solids.

    Args:
        solids: One or more Solid objects or sequences of Solid. Nested sequences are
            flattened before processing.

    Returns:
        Solid: The overlap region as a single solid.

    Usage:
        Accepts one or more solids, including nested sequences, and returns a single
        `Solid`. If the inputs do not overlap meaningfully, the API raises a clear
        error instead of returning an empty list.
    """
    try:
        remaining = _flatten_boolean_solids(solids, "intersect_rsolid")

        if not remaining:
            raise ValueError("intersect_rsolid 至少需要一个Solid输入")

        if len(remaining) == 1:
            return remaining[0]

        # 从第一个实体开始，依次与后续实体进行交集运算
        result_solid = remaining[0]
        deltas: List[TopoDelta] = []
        merged_delta_entries: Dict[str, Dict[str, object]] = {}
        intersect_performed = False

        for i in range(1, len(remaining)):
            candidate = remaining[i]

            s1 = result_solid.wrapped
            s2 = candidate.wrapped

            if s1.IsNull() or s2.IsNull():
                raise ValueError("输入实体无效，无法进行交集运算。")

            tracked = tracked_intersect(result_solid, candidate)
            if tracked.solid is None:
                raise ValueError("交集结果为空或 OCC 未返回有效实体")

            result_solid = tracked.solid
            deltas.append(tracked.delta)
            merged_delta_entries.update(
                cast(Dict[str, Dict[str, object]], tracked.delta_entries)
            )
            intersect_performed = True

            # 检查交集是否为空
            if result_solid.get_volume() < 1e-12:
                raise ValueError("交集结果为空或体积过小")

        all_metadata: dict = {}
        for solid in remaining:
            all_metadata.update(solid._metadata)

        result_solid._metadata = all_metadata
        result_solid._apply_tag("solid.boolean.intersect", propagate=False)

        merged_delta = _merge_topo_deltas(deltas)
        if intersect_performed and merged_delta is not None:
            result_solid = _finalize_tracked_solid(
                result_solid,
                op=_OP_MAKE_INTERSECT_RSOLID,
                params={"input_count": len(remaining)},
                source_solids=remaining,
                delta=merged_delta,
                delta_entries=merged_delta_entries or None,
                input_shapes=remaining,
            )
        else:
            _attach_track_summary(result_solid, op=_OP_MAKE_INTERSECT_RSOLID)
            record_operation_if_active(
                op=_OP_MAKE_INTERSECT_RSOLID,
                params={"input_count": len(remaining)},
                outputs=result_solid,
                input_shapes=remaining,
                context=_current_context_metadata(),
            )

        return result_solid
    except Exception as e:
        _wrap_public_api_error(
            operation="intersect_rsolid",
            what_happened="Failed to compute the boolean intersection.",
            possible_causes=[
                "One or more inputs are not Solid objects.",
                "At least one input solid is invalid.",
                "The solids do not overlap enough to produce a non-empty single solid.",
                "The kernel could not compute a stable overlap region.",
            ],
            how_to_fix=[
                "Pass only valid Solid objects.",
                "Verify that the solids truly overlap in space.",
                "Move the solids so they share a meaningful overlap volume before intersecting.",
            ],
            error=e,
        )


# =============================================================================
# 2D Face boolean operations
# =============================================================================


def _extract_single_face(shape_ocp, operation: str) -> Face:
    """Extract exactly one Face from an OCP shape result."""
    result_faces = faces_of_ocp(shape_ocp)
    if len(result_faces) != 1:
        raise ValueError(
            f"{operation} expected exactly 1 face in the result, got {len(result_faces)}"
        )
    return Face(result_faces[0])


def make_2d_cut_rface(body: Face, tool: Face) -> Face:
    """Subtract one 2D face from another (2D boolean difference).

    Parameters
    ----------
    body : Face
        The face to subtract from.
    tool : Face
        The face to subtract (the cutter).

    Returns
    -------
    Face
        The resulting face after subtraction.  The result may contain
        inner wires (holes) if the tool was fully inside the body.
    """
    try:
        if not isinstance(body, Face):
            raise ValueError("body must be a Face")
        if not isinstance(tool, Face):
            raise ValueError("tool must be a Face")

        result_shape = cut_shapes(body.wrapped, [tool.wrapped])
        result_face = _extract_single_face(result_shape, "make_2d_cut_rface")

        result_face._metadata = body._metadata.copy()

        return cast(
            Face,
            _finalize_derived_shape(
                result_face,
                op=_OP_MAKE_CUT_RFACE,
                params={},
                input_shapes=[body, tool],
                tags={"derived", "face"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_2d_cut_rface",
            what_happened="Failed to subtract one face from another.",
            possible_causes=[
                "The body or tool is not a Face.",
                "The faces do not overlap or are not coplanar.",
                "The kernel could not compute a stable 2D difference.",
            ],
            how_to_fix=[
                "Pass two valid Face objects.",
                "Ensure both faces lie on the same plane.",
                "Verify the tool face overlaps the body face.",
            ],
            error=e,
        )


def make_2d_union_rface(face_a: Face, face_b: Face) -> Face:
    """Compute the boolean union of two 2D faces.

    Parameters
    ----------
    face_a : Face
        First face.
    face_b : Face
        Second face.

    Returns
    -------
    Face
        The merged face.  Both inputs must overlap or touch so that the
        result is a single connected face.
    """
    try:
        if not isinstance(face_a, Face):
            raise ValueError("face_a must be a Face")
        if not isinstance(face_b, Face):
            raise ValueError("face_b must be a Face")

        result_shape = fuse_shapes([face_a.wrapped, face_b.wrapped], clean=True)
        result_face = _extract_single_face(result_shape, "make_2d_union_rface")

        result_face._metadata = {**face_a._metadata, **face_b._metadata}

        return cast(
            Face,
            _finalize_derived_shape(
                result_face,
                op=_OP_MAKE_UNION_RFACE,
                params={},
                input_shapes=[face_a, face_b],
                tags={"derived", "face"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_2d_union_rface",
            what_happened="Failed to union two faces.",
            possible_causes=[
                "One or both inputs are not Face objects.",
                "The faces do not overlap or touch.",
                "The faces are not coplanar.",
            ],
            how_to_fix=[
                "Pass two valid Face objects.",
                "Ensure the faces overlap or share a boundary.",
                "Ensure both faces lie on the same plane.",
            ],
            error=e,
        )


def make_2d_intersect_rface(face_a: Face, face_b: Face) -> Face:
    """Compute the boolean intersection of two 2D faces.

    Parameters
    ----------
    face_a : Face
        First face.
    face_b : Face
        Second face.

    Returns
    -------
    Face
        The overlapping region of the two faces.
    """
    try:
        if not isinstance(face_a, Face):
            raise ValueError("face_a must be a Face")
        if not isinstance(face_b, Face):
            raise ValueError("face_b must be a Face")

        result_shape = common_shapes([face_a.wrapped, face_b.wrapped])
        result_face = _extract_single_face(result_shape, "make_2d_intersect_rface")

        result_face._metadata = {**face_a._metadata, **face_b._metadata}

        return cast(
            Face,
            _finalize_derived_shape(
                result_face,
                op=_OP_MAKE_INTERSECT_RFACE,
                params={},
                input_shapes=[face_a, face_b],
                tags={"derived", "face"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_2d_intersect_rface",
            what_happened="Failed to intersect two faces.",
            possible_causes=[
                "One or both inputs are not Face objects.",
                "The faces do not overlap.",
                "The faces are not coplanar.",
            ],
            how_to_fix=[
                "Pass two valid Face objects.",
                "Ensure the faces have a non-empty overlap region.",
                "Ensure both faces lie on the same plane.",
            ],
            error=e,
        )


# =============================================================================
# Product semantic functions
# =============================================================================


def make_material_rmaterial(
    material_id: str,
    name: Optional[str] = None,
    density: Optional[float] = None,
    density_unit: Optional[str] = None,
    color: Optional[Tuple[float, float, float]] = None,
) -> Material:
    """Create a material definition for later Part assignment.

    Material is deliberately separate from `make_part_rpart(...)`; the only
    correct workflow is to create a material and then assign it to a Part with
    `assign_material_rpart(...)`.
    """

    try:
        material = Material(
            material_id,
            name=name,
            density=density,
            density_unit=density_unit,
            color=color,
        )
        _reserve_semantic_id("material", material.material_id)
        record_operation_if_active(
            _OP_MAKE_MATERIAL_RMATERIAL,
            _material_params(material),
            outputs=material,
            semantic_delta=_semantic_created(
                "Material", material.material_id, material.to_dict()
            ),
            context=_current_context_metadata(),
        )
        return material
    except Exception as e:
        _wrap_public_api_error(
            operation="make_material_rmaterial",
            what_happened="Failed to create the material definition.",
            possible_causes=[
                "The material_id is empty or uses unsupported characters.",
                "The density is non-finite, non-positive, or missing a density_unit.",
                "The color is not a 3-tuple in the [0.0, 1.0] range.",
            ],
            how_to_fix=[
                "Use a stable identifier such as 'aluminum_6061'.",
                "Provide density and density_unit together, or omit both.",
                "Pass RGB color components as floats between 0.0 and 1.0.",
            ],
            error=e,
        )


def make_placement_rplacement(
    origin: Tuple[float, float, float],
    x_axis: Tuple[float, float, float] = (1.0, 0.0, 0.0),
    y_axis: Tuple[float, float, float] = (0.0, 1.0, 0.0),
) -> Placement:
    """Create a canonical right-handed component placement.

    The placement maps child-local coordinates into parent assembly coordinates
    using one representation only: origin plus child x/y axes in parent space.
    """

    try:
        placement = Placement(origin, x_axis=x_axis, y_axis=y_axis)
        record_operation_if_active(
            _OP_MAKE_PLACEMENT_RPLACEMENT,
            _placement_params(placement),
            outputs=placement,
            context=_current_context_metadata(),
        )
        return placement
    except Exception as e:
        _wrap_public_api_error(
            operation="make_placement_rplacement",
            what_happened="Failed to create the placement.",
            possible_causes=[
                "The origin is not a finite 3D point.",
                "One of the axes is zero-length or non-finite.",
                "x_axis and y_axis are not orthogonal.",
            ],
            how_to_fix=[
                "Pass origin, x_axis, and y_axis as finite 3-element tuples.",
                "Use one canonical representation; do not mix Euler, quaternion, or axis-angle payloads.",
                "Make sure x_axis and y_axis form a right-handed frame.",
            ],
            error=e,
        )


def identity_placement_rplacement() -> Placement:
    """Create an identity placement."""

    try:
        placement = identity_placement()
        record_operation_if_active(
            _OP_MAKE_IDENTITY_PLACEMENT_RPLACEMENT,
            _placement_params(placement),
            outputs=placement,
            context=_current_context_metadata(),
        )
        return placement
    except Exception as e:
        _wrap_public_api_error(
            operation="identity_placement_rplacement",
            what_happened="Failed to create the identity placement.",
            possible_causes=["Internal placement validation failed."],
            how_to_fix=["Report this as a SimpleCADAPI bug if it reproduces."],
            error=e,
        )


def make_part_rpart(
    part_id: str,
    body: Solid,
    name: Optional[str] = None,
) -> Part:
    """Wrap exactly one Solid as a semantic single-body Part."""

    try:
        part = Part(part_id, body, name=name)
        _reserve_semantic_id("part", part.part_id)
        record_operation_if_active(
            _OP_MAKE_PART_RPART,
            _part_params(part),
            outputs=part,
            input_shapes=[body],
            semantic_delta=_semantic_created("Part", part.part_id, part.to_dict()),
            context=_current_context_metadata(),
        )
        return part
    except Exception as e:
        _wrap_public_api_error(
            operation="make_part_rpart",
            what_happened="Failed to create the single-body Part.",
            possible_causes=[
                "The part_id is empty or uses unsupported characters.",
                "The body is not a Solid.",
                "A Part with the same part_id already exists in the active GraphSession.",
            ],
            how_to_fix=[
                "Pass a stable part_id such as 'base_plate'.",
                "Union intended multiple bodies into one Solid before creating the Part.",
                "Do not pass material to make_part_rpart; use assign_material_rpart instead.",
            ],
            error=e,
        )


def assign_material_rpart(part: Part, material: Material) -> Part:
    """Assign a Material to a Part and return the updated Part."""

    try:
        if not isinstance(part, Part):
            raise TypeError("part must be a Part")
        if not isinstance(material, Material):
            raise TypeError("material must be a Material")
        result = part.with_material(material)
        record_operation_if_active(
            _OP_MAKE_ASSIGN_MATERIAL_RPART,
            {
                "part_id": part.part_id,
                "material_id": material.material_id,
                "material": _material_params(material),
            },
            outputs=result,
            input_shapes=[part, material],
            semantic_delta=_semantic_modified(
                "Part",
                part.part_id,
                {"material_id": material.material_id},
            ),
            context=_current_context_metadata(),
        )
        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="assign_material_rpart",
            what_happened="Failed to assign the material to the Part.",
            possible_causes=[
                "The part input is not a Part.",
                "The material input is not a Material.",
            ],
            how_to_fix=[
                "Create parts with make_part_rpart(...).",
                "Create materials with make_material_rmaterial(...).",
            ],
            error=e,
        )


def make_assembly_rassembly(
    assembly_id: str,
    name: Optional[str] = None,
) -> Assembly:
    """Create an empty assembly product structure."""

    try:
        assembly = Assembly(assembly_id, name=name)
        _reserve_semantic_id("assembly", assembly.assembly_id)
        record_operation_if_active(
            _OP_MAKE_ASSEMBLY_RASSEMBLY,
            _assembly_params(assembly),
            outputs=assembly,
            semantic_delta=_semantic_created(
                "Assembly", assembly.assembly_id, assembly.to_dict()
            ),
            context=_current_context_metadata(),
        )
        return assembly
    except Exception as e:
        _wrap_public_api_error(
            operation="make_assembly_rassembly",
            what_happened="Failed to create the assembly.",
            possible_causes=[
                "The assembly_id is empty or uses unsupported characters.",
                "An Assembly with the same assembly_id already exists in the active GraphSession.",
            ],
            how_to_fix=["Pass a stable assembly_id such as 'fixture_assembly'."],
            error=e,
        )


def add_component_rassembly(
    assembly: Assembly,
    item: Union[Part, Assembly],
    component_id: str,
    placement: Placement,
    name: Optional[str] = None,
) -> Assembly:
    """Add a placed Part or subassembly component instance to an Assembly."""

    try:
        if not isinstance(assembly, Assembly):
            raise TypeError("assembly must be an Assembly")
        if not isinstance(item, (Part, Assembly)):
            raise TypeError("item must be a Part or Assembly")
        if not isinstance(placement, Placement):
            raise TypeError("placement must be a Placement")
        component = Component(component_id, item, placement, name=name)
        result = assembly.with_component(component)
        item_kind = "assembly" if isinstance(item, Assembly) else "part"
        item_id = item.assembly_id if isinstance(item, Assembly) else item.part_id
        record_operation_if_active(
            _OP_MAKE_ADD_COMPONENT_RASSEMBLY,
            {
                "assembly_id": assembly.assembly_id,
                "component_id": component.component_id,
                "name": component.name,
                "item_kind": item_kind,
                "item_id": item_id,
            },
            outputs=result,
            input_shapes=[assembly, item, placement],
            semantic_delta=SemanticDelta(
                created=(
                    SemanticRef(
                        graph_id="pending",
                        node_id="pending",
                        entity_type="Component",
                        entity_id=f"{assembly.assembly_id}:{component.component_id}",
                    ),
                ),
                modified=(
                    SemanticRef(
                        graph_id="pending",
                        node_id="pending",
                        entity_type="Assembly",
                        entity_id=assembly.assembly_id,
                    ),
                ),
                metadata={"component": component.to_dict()},
            ),
            context=_current_context_metadata(),
        )
        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="add_component_rassembly",
            what_happened="Failed to add the component to the assembly.",
            possible_causes=[
                "The assembly input is not an Assembly.",
                "The item input is not a Part or Assembly.",
                "The component_id is empty, malformed, or duplicated in the assembly.",
                "The placement is invalid or missing.",
                "Adding this subassembly would create an assembly cycle.",
            ],
            how_to_fix=[
                "Wrap solids explicitly with make_part_rpart before adding them to assemblies.",
                "Use a unique component_id within the parent assembly.",
                "Create placements with make_placement_rplacement or identity_placement_rplacement.",
            ],
            error=e,
        )


def place_component_rassembly(
    assembly: Assembly,
    component_id: str,
    placement: Placement,
) -> Assembly:
    """Move an existing assembly component by replacing its placement."""

    try:
        if not isinstance(assembly, Assembly):
            raise TypeError("assembly must be an Assembly")
        if not isinstance(placement, Placement):
            raise TypeError("placement must be a Placement")
        result = assembly.with_component_placement(component_id, placement)
        record_operation_if_active(
            _OP_MAKE_PLACE_COMPONENT_RASSEMBLY,
            {
                "assembly_id": assembly.assembly_id,
                "component_id": component_id,
            },
            outputs=result,
            input_shapes=[assembly, placement],
            semantic_delta=_semantic_modified(
                "Component",
                f"{assembly.assembly_id}:{component_id}",
                {"placement": placement.to_dict()},
            ),
            context=_current_context_metadata(),
        )
        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="place_component_rassembly",
            what_happened="Failed to place the assembly component.",
            possible_causes=[
                "The assembly input is not an Assembly.",
                "The component_id does not exist in the assembly.",
                "The placement is invalid or missing.",
            ],
            how_to_fix=[
                "Use add_component_rassembly before placing a component.",
                "Use a component_id returned in assembly.component_ids().",
                "Create placements with make_placement_rplacement.",
            ],
            error=e,
        )


def _make_geometry_backed_connector(
    connector_id: str,
    shape: AnyShape,
    *,
    op: str,
    operation_name: str,
    name: Optional[str] = None,
    flip: bool = False,
) -> Connector:
    source_shape = _selection_source_for_shape(shape) or shape
    node_ids = _ensure_geo_selection_node_ids(source_shape, [shape])
    source_node_id = node_ids[0] if node_ids else None
    geo_selector = _make_geo_selector(shape, source_shape=source_shape)
    kind = _shape_kind_token(shape)
    geometry_ref = GeometryRef(
        kind=kind,
        source_node_id=source_node_id,
        geo_selector=geo_selector,
        flip=bool(flip),
    )
    connector = Connector(connector_id, geometry_ref, name=name)
    record_operation_if_active(
        op,
        _connector_params(connector),
        outputs=connector,
        input_shapes=[shape],
        context=_current_context_metadata(),
    )
    return connector


def make_face_connector_rconnector(
    connector_id: str,
    face: Face,
    name: Optional[str] = None,
    flip: bool = False,
) -> Connector:
    """Create a connector anchored to a Face.

    Z axis follows the face normal; origin is the face center.
    Set flip=True to negate the Z axis (point it opposite to the normal).
    """
    try:
        if not isinstance(face, Face):
            raise TypeError("face must be a Face")
        return _make_geometry_backed_connector(
            connector_id,
            face,
            op=_OP_MAKE_FACE_CONNECTOR_RCONNECTOR,
            operation_name="make_face_connector_rconnector",
            name=name,
            flip=flip,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_face_connector_rconnector",
            what_happened="Failed to create the face connector.",
            possible_causes=[
                "The connector_id is empty or malformed.",
                "The face is not a valid Face object.",
            ],
            how_to_fix=[
                "Use a stable connector_id such as 'mount_face'.",
                "Select a face via ql.faces().resolve(solid) or solid.get_faces()[i].",
            ],
            error=e,
        )


def make_edge_connector_rconnector(
    connector_id: str,
    edge: Edge,
    name: Optional[str] = None,
    flip: bool = False,
) -> Connector:
    """Create a connector anchored to an Edge.

    Z axis follows the edge direction (start->end); origin is the edge midpoint.
    Set flip=True to negate the Z axis.
    """
    try:
        if not isinstance(edge, Edge):
            raise TypeError("edge must be an Edge")
        return _make_geometry_backed_connector(
            connector_id,
            edge,
            op=_OP_MAKE_EDGE_CONNECTOR_RCONNECTOR,
            operation_name="make_edge_connector_rconnector",
            name=name,
            flip=flip,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_edge_connector_rconnector",
            what_happened="Failed to create the edge connector.",
            possible_causes=[
                "The connector_id is empty or malformed.",
                "The edge is not a valid Edge object.",
            ],
            how_to_fix=[
                "Use a stable connector_id such as 'hinge_axis'.",
                "Select an edge via ql.edges().resolve(solid) or solid.get_edges()[i].",
            ],
            error=e,
        )


def make_vertex_connector_rconnector(
    connector_id: str,
    vertex: Vertex,
    name: Optional[str] = None,
    flip: bool = False,
) -> Connector:
    """Create a connector anchored to a Vertex.

    Origin is the vertex point; axes are identity.
    flip has no effect on vertex connectors (no direction).
    """
    try:
        if not isinstance(vertex, Vertex):
            raise TypeError("vertex must be a Vertex")
        return _make_geometry_backed_connector(
            connector_id,
            vertex,
            op=_OP_MAKE_VERTEX_CONNECTOR_RCONNECTOR,
            operation_name="make_vertex_connector_rconnector",
            name=name,
            flip=flip,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_vertex_connector_rconnector",
            what_happened="Failed to create the vertex connector.",
            possible_causes=[
                "The connector_id is empty or malformed.",
                "The vertex is not a valid Vertex object.",
            ],
            how_to_fix=[
                "Use a stable connector_id such as 'pivot_point'.",
                "Select a vertex via ql.vertices().resolve(solid) or solid.get_vertices()[i].",
            ],
            error=e,
        )


def make_placement_connector_rconnector(
    connector_id: str,
    placement: Placement,
    name: Optional[str] = None,
) -> Connector:
    """Create a connector anchored to an explicit local placement frame.

    Use this when a datum should be defined by a stable coordinate frame
    instead of a selected BREP face, edge, or vertex.
    """

    try:
        if not isinstance(placement, Placement):
            raise TypeError("placement must be a Placement")
        anchor = ConnectorAnchor("placement", placement=placement)
        connector = Connector(connector_id, None, name=name, anchor=anchor)
        record_operation_if_active(
            _OP_MAKE_PLACEMENT_CONNECTOR_RCONNECTOR,
            {
                "connector_id": connector.connector_id,
                "placement": placement.to_dict(),
                "name": connector.name,
            },
            outputs=connector,
            input_shapes=[placement],
            context=_current_context_metadata(),
        )
        return connector
    except Exception as e:
        _wrap_public_api_error(
            operation="make_placement_connector_rconnector",
            what_happened="Failed to create the placement connector.",
            possible_causes=[
                "The connector_id is empty or malformed.",
                "The placement input is not a Placement.",
            ],
            how_to_fix=[
                "Create placements with make_placement_rplacement.",
                "Use a stable connector_id such as 'bearing_axis'.",
            ],
            error=e,
        )


def add_connector_rpart(part: Part, connector: Connector) -> Part:
    """Attach a connector datum frame to a Part definition."""

    try:
        if not isinstance(part, Part):
            raise TypeError("part must be a Part")
        result = part.with_connector(connector)
        record_operation_if_active(
            _OP_MAKE_ADD_CONNECTOR_RPART,
            {"part_id": part.part_id, "connector_id": connector.connector_id},
            outputs=result,
            input_shapes=[part, connector],
            semantic_delta=_semantic_modified(
                "Part", part.part_id, {"connector": connector.to_dict()}
            ),
            context=_current_context_metadata(),
        )
        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="add_connector_rpart",
            what_happened="Failed to add the connector to the Part.",
            possible_causes=[
                "The part input is not a Part.",
                "The connector input is not a Connector.",
                "The connector_id is duplicated in the Part.",
            ],
            how_to_fix=[
                "Create a connector with make_face_connector_rconnector, make_edge_connector_rconnector, or make_vertex_connector_rconnector.",
                "Use unique connector ids within one Part.",
            ],
            error=e,
        )


def add_connector_rassembly(assembly: Assembly, connector: Connector) -> Assembly:
    """Attach a connector datum frame to an Assembly definition."""

    try:
        if not isinstance(assembly, Assembly):
            raise TypeError("assembly must be an Assembly")
        result = assembly.with_connector(connector)
        record_operation_if_active(
            _OP_MAKE_ADD_CONNECTOR_RASSEMBLY,
            {
                "assembly_id": assembly.assembly_id,
                "connector_id": connector.connector_id,
            },
            outputs=result,
            input_shapes=[assembly, connector],
            semantic_delta=_semantic_modified(
                "Assembly", assembly.assembly_id, {"connector": connector.to_dict()}
            ),
            context=_current_context_metadata(),
        )
        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="add_connector_rassembly",
            what_happened="Failed to add the connector to the Assembly.",
            possible_causes=[
                "The assembly input is not an Assembly.",
                "The connector input is not a Connector.",
                "The connector_id is duplicated in the Assembly.",
            ],
            how_to_fix=[
                "Create a connector with make_face_connector_rconnector, make_edge_connector_rconnector, or make_vertex_connector_rconnector.",
                "Use unique connector ids within one Assembly.",
            ],
            error=e,
        )


def forward_connector_rassembly(
    assembly: Assembly,
    connector_id: str,
    source_component_id: str,
    source_connector_id: str,
    name: Optional[str] = None,
    offset: Optional[Placement] = None,
) -> Assembly:
    """Expose an internal component connector as an assembly-level connector.

    The forwarded connector resolves to `source_component.placement *
    source_connector.placement`, followed by the optional `offset` placement.
    Parent assemblies can constrain to the subassembly's public connector
    without depending on its private component structure.
    """

    try:
        if not isinstance(assembly, Assembly):
            raise TypeError("assembly must be an Assembly")
        if offset is not None and not isinstance(offset, Placement):
            raise TypeError("offset must be a Placement")
        anchor = ConnectorAnchor(
            "forwarded",
            source_component_id=source_component_id,
            source_connector_id=source_connector_id,
            offset=offset,
        )
        connector = Connector(connector_id, None, name=name, anchor=anchor)
        result = assembly.with_connector(connector)
        record_operation_if_active(
            _OP_MAKE_FORWARD_CONNECTOR_RASSEMBLY,
            {
                "assembly_id": assembly.assembly_id,
                "connector_id": connector.connector_id,
                "source_component_id": anchor.source_component_id,
                "source_connector_id": anchor.source_connector_id,
                "name": connector.name,
                "offset": offset.to_dict() if offset is not None else None,
            },
            outputs=result,
            input_shapes=[assembly] + ([offset] if offset is not None else []),
            semantic_delta=_semantic_modified(
                "Assembly", assembly.assembly_id, {"connector": connector.to_dict()}
            ),
            context=_current_context_metadata(),
        )
        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="forward_connector_rassembly",
            what_happened="Failed to forward the assembly connector.",
            possible_causes=[
                "The assembly input is not an Assembly.",
                "The connector_id is duplicated in the Assembly.",
                "The source component or source connector does not exist.",
                "The optional offset is not a Placement.",
            ],
            how_to_fix=[
                "Add the source component before forwarding its connector.",
                "Use a connector_id unique within the Assembly.",
                "Create offsets with make_placement_rplacement when needed.",
            ],
            error=e,
        )


def make_connector_ref_rconnectorref(
    component_id: str, connector_id: str
) -> ConnectorRef:
    """Reference a connector through a component instance."""

    try:
        connector_ref = ConnectorRef(component_id, connector_id)
        record_operation_if_active(
            _OP_MAKE_CONNECTOR_REF_RCONNECTORREF,
            _connector_ref_params(connector_ref),
            outputs=connector_ref,
            context=_current_context_metadata(),
        )
        return connector_ref
    except Exception as e:
        _wrap_public_api_error(
            operation="make_connector_ref_rconnectorref",
            what_happened="Failed to create the connector reference.",
            possible_causes=["The component_id or connector_id is empty or malformed."],
            how_to_fix=["Use stable ids from the owning Assembly and component item."],
            error=e,
        )


def make_scalar_limit_rscalarlimit(
    lower_value: float, upper_value: float
) -> ScalarLimit:
    """Create a closed scalar limit for driven constraint coordinates."""

    try:
        limit = ScalarLimit(lower_value, upper_value)
        record_operation_if_active(
            _OP_MAKE_SCALAR_LIMIT_RSCALARLIMIT,
            _scalar_limit_params(limit),
            outputs=limit,
            context=_current_context_metadata(),
        )
        return limit
    except Exception as e:
        _wrap_public_api_error(
            operation="make_scalar_limit_rscalarlimit",
            what_happened="Failed to create the scalar limit.",
            possible_causes=[
                "One of the limit values is non-finite.",
                "lower_value is greater than upper_value.",
            ],
            how_to_fix=["Pass finite lower and upper values in increasing order."],
            error=e,
        )


def ground_component_rassembly(assembly: Assembly, component_id: str) -> Assembly:
    """Ground a component at its current authored placement."""

    try:
        if not isinstance(assembly, Assembly):
            raise TypeError("assembly must be an Assembly")
        result = assembly.with_grounded_component(component_id)
        record_operation_if_active(
            _OP_MAKE_GROUND_COMPONENT_RASSEMBLY,
            {"assembly_id": assembly.assembly_id, "component_id": component_id},
            outputs=result,
            input_shapes=[assembly],
            semantic_delta=_semantic_modified(
                "Assembly",
                assembly.assembly_id,
                {"grounded_component_id": component_id},
            ),
            context=_current_context_metadata(),
        )
        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="ground_component_rassembly",
            what_happened="Failed to ground the assembly component.",
            possible_causes=[
                "The assembly input is not an Assembly.",
                "The component_id does not exist in the Assembly.",
            ],
            how_to_fix=["Use a component_id already added to the Assembly."],
            error=e,
        )


def unground_component_rassembly(assembly: Assembly, component_id: str) -> Assembly:
    """Remove a component grounding marker."""

    try:
        if not isinstance(assembly, Assembly):
            raise TypeError("assembly must be an Assembly")
        result = assembly.without_grounded_component(component_id)
        record_operation_if_active(
            _OP_MAKE_UNGROUND_COMPONENT_RASSEMBLY,
            {"assembly_id": assembly.assembly_id, "component_id": component_id},
            outputs=result,
            input_shapes=[assembly],
            semantic_delta=_semantic_modified(
                "Assembly",
                assembly.assembly_id,
                {"ungrounded_component_id": component_id},
            ),
            context=_current_context_metadata(),
        )
        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="unground_component_rassembly",
            what_happened="Failed to unground the assembly component.",
            possible_causes=[
                "The assembly input is not an Assembly.",
                "The component_id does not exist in the Assembly.",
            ],
            how_to_fix=["Use a component_id already added to the Assembly."],
            error=e,
        )


def add_fixed_constraint_rassembly(
    assembly: Assembly,
    constraint_id: str,
    connector_a: ConnectorRef,
    connector_b: ConnectorRef,
    name: Optional[str] = None,
) -> Assembly:
    """Constrain two component connectors to the same frame."""

    return _add_constraint_rassembly(
        assembly,
        Constraint(
            constraint_id,
            "fixed",
            connector_a,
            connector_b,
            name=name,
        ),
        _OP_MAKE_FIXED_CONSTRAINT_RASSEMBLY,
        "add_fixed_constraint_rassembly",
    )


def add_revolute_constraint_rassembly(
    assembly: Assembly,
    constraint_id: str,
    connector_a: ConnectorRef,
    connector_b: ConnectorRef,
    drive_angle_degrees: Optional[float] = None,
    angle_limit: Optional[ScalarLimit] = None,
    name: Optional[str] = None,
) -> Assembly:
    """Constrain two connectors as a revolute axis pair."""

    return _add_constraint_rassembly(
        assembly,
        Constraint(
            constraint_id,
            "revolute",
            connector_a,
            connector_b,
            drive_angle_degrees=drive_angle_degrees,
            angle_limit=angle_limit,
            name=name,
        ),
        _OP_MAKE_REVOLUTE_CONSTRAINT_RASSEMBLY,
        "add_revolute_constraint_rassembly",
    )


def add_prismatic_constraint_rassembly(
    assembly: Assembly,
    constraint_id: str,
    connector_a: ConnectorRef,
    connector_b: ConnectorRef,
    drive_distance: Optional[float] = None,
    distance_limit: Optional[ScalarLimit] = None,
    name: Optional[str] = None,
) -> Assembly:
    """Constrain two connectors as a prismatic slider pair."""

    return _add_constraint_rassembly(
        assembly,
        Constraint(
            constraint_id,
            "prismatic",
            connector_a,
            connector_b,
            drive_distance=drive_distance,
            distance_limit=distance_limit,
            name=name,
        ),
        _OP_MAKE_PRISMATIC_CONSTRAINT_RASSEMBLY,
        "add_prismatic_constraint_rassembly",
    )


def add_gear_constraint_rassembly(
    assembly: Assembly,
    constraint_id: str,
    connector_a: ConnectorRef,
    connector_b: ConnectorRef,
    pitch_radius_a: float,
    pitch_radius_b: float,
    phase_offset: Optional[float] = None,
    name: Optional[str] = None,
) -> Assembly:
    """Couple two revolute axes as meshing gears with inverse rotation."""

    constraint = Constraint(
        constraint_id,
        "gear",
        connector_a,
        connector_b,
        pitch_radius_a=pitch_radius_a,
        pitch_radius_b=pitch_radius_b,
        phase_offset=phase_offset,
        name=name,
    )
    if phase_offset is None:
        constraint = Constraint(
            constraint_id,
            "gear",
            connector_a,
            connector_b,
            pitch_radius_a=pitch_radius_a,
            pitch_radius_b=pitch_radius_b,
            phase_offset=coupling_phase_offset(assembly, constraint),
            name=name,
        )
    return _add_constraint_rassembly(
        assembly,
        constraint,
        _OP_MAKE_GEAR_CONSTRAINT_RASSEMBLY,
        "add_gear_constraint_rassembly",
    )


def add_belt_constraint_rassembly(
    assembly: Assembly,
    constraint_id: str,
    connector_a: ConnectorRef,
    connector_b: ConnectorRef,
    pulley_radius_a: float,
    pulley_radius_b: float,
    phase_offset: Optional[float] = None,
    name: Optional[str] = None,
) -> Assembly:
    """Couple two revolute axes as belt-linked pulleys with same-direction rotation."""

    constraint = Constraint(
        constraint_id,
        "belt",
        connector_a,
        connector_b,
        pulley_radius_a=pulley_radius_a,
        pulley_radius_b=pulley_radius_b,
        phase_offset=phase_offset,
        name=name,
    )
    if phase_offset is None:
        constraint = Constraint(
            constraint_id,
            "belt",
            connector_a,
            connector_b,
            pulley_radius_a=pulley_radius_a,
            pulley_radius_b=pulley_radius_b,
            phase_offset=coupling_phase_offset(assembly, constraint),
            name=name,
        )
    return _add_constraint_rassembly(
        assembly,
        constraint,
        _OP_MAKE_BELT_CONSTRAINT_RASSEMBLY,
        "add_belt_constraint_rassembly",
    )


def add_rack_pinion_constraint_rassembly(
    assembly: Assembly,
    constraint_id: str,
    rack_connector: ConnectorRef,
    pinion_connector: ConnectorRef,
    pitch_radius: float,
    phase_offset: Optional[float] = None,
    name: Optional[str] = None,
) -> Assembly:
    """Couple a prismatic rack axis to a revolute pinion axis."""

    constraint = Constraint(
        constraint_id,
        "rack_pinion",
        rack_connector,
        pinion_connector,
        pitch_radius=pitch_radius,
        phase_offset=phase_offset,
        name=name,
    )
    if phase_offset is None:
        constraint = Constraint(
            constraint_id,
            "rack_pinion",
            rack_connector,
            pinion_connector,
            pitch_radius=pitch_radius,
            phase_offset=coupling_phase_offset(assembly, constraint),
            name=name,
        )
    return _add_constraint_rassembly(
        assembly,
        constraint,
        _OP_MAKE_RACK_PINION_CONSTRAINT_RASSEMBLY,
        "add_rack_pinion_constraint_rassembly",
    )


def _add_constraint_rassembly(
    assembly: Assembly,
    constraint: Constraint,
    op_name: str,
    public_name: str,
) -> Assembly:
    try:
        if not isinstance(assembly, Assembly):
            raise TypeError("assembly must be an Assembly")
        result = assembly.with_constraint(constraint)
        inputs: List[object] = [
            assembly,
            constraint.connector_a,
            constraint.connector_b,
        ]
        if constraint.distance_limit is not None:
            inputs.append(constraint.distance_limit)
        if constraint.angle_limit is not None:
            inputs.append(constraint.angle_limit)
        record_operation_if_active(
            op_name,
            _constraint_params(constraint),
            outputs=result,
            input_shapes=inputs,
            semantic_delta=_semantic_modified(
                "Assembly", assembly.assembly_id, {"constraint": constraint.to_dict()}
            ),
            context=_current_context_metadata(),
        )
        return result
    except Exception as e:
        _wrap_public_api_error(
            operation=public_name,
            what_happened="Failed to add the assembly constraint.",
            possible_causes=[
                "The assembly input is not an Assembly.",
                "A connector ref references a missing component or connector.",
                "The constraint_id is duplicated in the Assembly.",
                "A drive value violates its scalar limit.",
            ],
            how_to_fix=[
                "Create connector refs with make_connector_ref_rconnectorref.",
                "Add connectors to Parts or Assemblies before adding constrained components.",
                "Use unique constraint ids within one Assembly.",
            ],
            error=e,
        )


def solve_assembly_constraints_rassembly(
    assembly: Assembly, strict: bool = True
) -> Assembly:
    """Solve fixed, revolute, and prismatic assembly constraints.

    Solving is limit-aware: when a constraint carries a ``ScalarLimit``
    (``angle_limit`` or ``distance_limit``), the drive scalar is clamped
    into the closed range before placement propagation.  When no drive
    scalar is present but a limit exists, the current relative-frame
    scalar is projected into the bounds.  Unresolvable closed kinematic
    loops fall back to a golden-section search over the limit bounds.

    A ``ConstraintReport`` is recorded on the returned assembly under the
    ``constraint_report`` runtime key for later inspection via
    ``inspect_assembly_constraints_rassembly``.
    """

    try:
        result = solve_assembly_constraints(assembly, strict=bool(strict))
        solved_component_placements = {
            component.component_id: component.placement.to_dict()
            for component in result.components
        }
        record_operation_if_active(
            _OP_MAKE_SOLVE_ASSEMBLY_CONSTRAINTS_RASSEMBLY,
            {
                "assembly_id": assembly.assembly_id,
                "strict": bool(strict),
                "component_placements": solved_component_placements,
            },
            outputs=result,
            input_shapes=[assembly],
            semantic_delta=_semantic_modified(
                "Assembly", assembly.assembly_id, {"constraints_solved": True}
            ),
            context=_current_context_metadata(),
        )
        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="solve_assembly_constraints_rassembly",
            what_happened="Failed to solve the assembly constraints.",
            possible_causes=[
                "No component is grounded.",
                "A constraint graph references missing connectors.",
                "A connected component cannot be reached from a grounded component.",
                "A closed-loop residual exceeds tolerance.",
            ],
            how_to_fix=[
                "Ground at least one component with ground_component_rassembly.",
                "Ensure every constrained component has the required connectors.",
                "Inspect constraint residuals before strict solving.",
            ],
            error=e,
        )


def measure_constraint_residual_rconstraintresidual(
    assembly: Assembly, constraint_id: str
) -> ConstraintResidual:
    """Measure residual for one assembly constraint without mutating the assembly."""

    return measure_constraint_residual(assembly, constraint_id)


def inspect_assembly_constraints_rconstraintreport(
    assembly: Assembly,
) -> ConstraintReport:
    """Inspect all assembly constraint residuals without mutating the assembly."""

    return inspect_assembly_constraints(assembly)


def _placed_solids_from_item(
    item: Union[Part, Assembly], placement: Placement
) -> List[Solid]:
    if isinstance(item, Part):
        placed = place_shape_ocp(
            item.body,
            placement.origin,
            placement.x_axis,
            placement.y_axis,
            placement.z_axis,
        )
        return [cast(Solid, placed)]
    if isinstance(item, Assembly):
        solids: List[Solid] = []
        for component in item.components:
            solids.extend(
                _placed_solids_from_item(
                    component.item,
                    compose_placements(placement, component.placement),
                )
            )
        return solids
    raise TypeError("item must be a Part or Assembly")


def make_compound_from_assembly_rcompound(assembly: Assembly) -> Compound:
    """Project an Assembly into an explicit flattened Compound geometry value."""

    try:
        if not isinstance(assembly, Assembly):
            raise TypeError("assembly must be an Assembly")
        if not assembly.components:
            raise ValueError("assembly must contain at least one component to project")
        solids = _placed_solids_from_item(assembly, identity_placement())
        if not solids:
            raise ValueError("assembly projection produced no solids")
        compound = Compound(make_compound_always([solid.wrapped for solid in solids]))
        compound.set_metadata(
            "assembly_projection",
            {
                "assembly_id": assembly.assembly_id,
                "component_count": len(assembly.components),
                "solid_count": len(solids),
            },
        )
        record_operation_if_active(
            _OP_MAKE_COMPOUND_FROM_ASSEMBLY_RCOMPOUND,
            {
                "assembly_id": assembly.assembly_id,
                "component_count": len(assembly.components),
            },
            outputs=compound,
            input_shapes=[assembly],
            semantic_delta=_semantic_modified(
                "Assembly",
                assembly.assembly_id,
                {"projection": "compound", "solid_count": len(solids)},
            ),
            context=_current_context_metadata(),
        )
        return compound
    except Exception as e:
        _wrap_public_api_error(
            operation="make_compound_from_assembly_rcompound",
            what_happened="Failed to project the assembly into a Compound.",
            possible_causes=[
                "The input is not an Assembly.",
                "The assembly has no components.",
                "A component placement is invalid.",
                "The kernel could not transform or combine the component bodies.",
            ],
            how_to_fix=[
                "Create an assembly with make_assembly_rassembly and add at least one component.",
                "Ensure every component references a valid Part or subassembly.",
                "Validate placements before projection.",
            ],
            error=e,
        )


# =============================================================================
# 导出函数
# =============================================================================


_EXPORTABLE_TYPES = (Compound, Solid, Face, Wire, Edge, Vertex)


def _normalize_shape_input(
    shapes: Union[AnyShape, Sequence[AnyShape]],
) -> List[AnyShape]:
    """Normalize export input into a flat list of shapes."""

    if isinstance(shapes, _EXPORTABLE_TYPES):
        return [shapes]

    if isinstance(shapes, Sequence) and not isinstance(shapes, (str, bytes)):
        normalized: List[AnyShape] = []
        for item in shapes:
            normalized.extend(_normalize_shape_input(cast(AnyShape, item)))
        return normalized

    raise ValueError(
        "export 函数只支持 Compound、Solid、Face、Wire、Edge、Vertex 或其序列类型的输入"
    )


def export_step(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None:
    """Export shapes to STEP.

    Args:
        shapes: A single exportable shape or any nested sequence of exportable
            shapes. Lists of Solid are supported directly, including pattern or
            explicitly collected multi-shape results.
        filename: Output STEP file path.

    Returns:
        None: Writes the provided shapes into one STEP file.

    Usage:
        Use this function when you want to export one shape or many shapes into the
        same STEP file. Passing `List[Solid]` is valid for pattern outputs or
        explicit shape collections. Boolean operations return a single `Solid`.

    Examples:
        main_body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
        left_cap = make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0))
        right_cap = make_sphere_rsolid(2.0, center=(12.0, 2.0, 2.0))
        body = union_rsolid(main_body, [left_cap, right_cap])

        export_step(body, "rounded_bar.step")
    """
    try:
        shape_list = _normalize_shape_input(shapes)

        export_step_shapes([shape.wrapped for shape in shape_list], filename)
    except Exception as e:
        _wrap_public_api_error(
            operation="export_step",
            what_happened="Failed to export the shape set to STEP.",
            possible_causes=[
                "One or more inputs are not exportable SimpleCAD shapes.",
                "The output path is invalid or not writable.",
                "The exporter rejected the provided geometry.",
            ],
            how_to_fix=[
                "Pass Compound, Solid, Face, Wire, Edge, Vertex, or sequences of those types.",
                "Use a writable file path ending in .step or .stp.",
                "If export still fails, inspect each input shape individually.",
            ],
            error=e,
        )


def export_stl(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None:
    """Export shapes to STL.

    Args:
        shapes: A single Compound, Solid, or Face, or any nested sequence of those.
            Lists of Solid are supported directly, including pattern or explicitly
            collected multi-shape results.
        filename: Output STL file path.

    Returns:
        None: Writes the provided shapes into one STL file.

    Usage:
        Use this function when you want to export one compound, solid, or face into
        the same STL file. Passing `List[Solid]` is valid for pattern outputs or
        explicit shape collections. Boolean operations return a single `Solid`.

    Examples:
        main_body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
        left_cap = make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0))
        right_cap = make_sphere_rsolid(2.0, center=(12.0, 2.0, 2.0))
        body = union_rsolid(main_body, [left_cap, right_cap])

        export_stl(body, "rounded_bar.stl")
    """
    try:
        shape_list = _normalize_shape_input(shapes)

        for shape in shape_list:
            if not isinstance(shape, (Compound, Solid, Face)):
                raise ValueError(
                    "export_stl函数只支持Compound、Solid和Face类型的几何体"
                )
        export_stl_shape(
            make_compound([shape.wrapped for shape in shape_list]), filename
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="export_stl",
            what_happened="Failed to export the shape set to STL.",
            possible_causes=[
                "One or more inputs are not Solid or Face objects.",
                "The output path is invalid or not writable.",
                "The exporter rejected the provided geometry.",
            ],
            how_to_fix=[
                "Pass Solid or Face objects, or sequences of them.",
                "Use a writable file path ending in .stl.",
                "If export still fails, isolate which shape triggers the exporter error.",
            ],
            error=e,
        )


def render_screenshot_rpath(
    shapes: Union[Solid, Sequence[Solid]],
    output_path: str,
    highlight_tags: Optional[Sequence[str]] = None,
    tag_labels: Optional[Dict[str, str]] = None,
    image_size: Tuple[int, int] = (1400, 900),
    view: Union[Tuple[float, float], str] = "auto",
    show_axes: bool = True,
    show_legend: bool = True,
    zoom: float = 4.0,
    show_callouts: bool = True,
) -> str:
    """Render a screenshot of shapes and save it to a file."""
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from matplotlib.colors import to_rgb
        from mpl_toolkits.mplot3d import proj3d
        from mpl_toolkits.mplot3d.art3d import Line3DCollection, Poly3DCollection

        shape_list = _normalize_shape_input(shapes)
        solids = [shape for shape in shape_list if isinstance(shape, Solid)]
        if not solids:
            raise ValueError("render_screenshot_rpath 仅支持 Solid 类型")

        background = "#111111"
        base_color = (0.6, 0.62, 0.64)
        highlight_colors: Dict[str, Tuple[float, float, float]] = {}
        fit_mode = "model"
        axis_scale = 1.6
        axis_fit_weight = 0.0
        wireframe_only = False
        mesh_tolerance = 0.35
        mesh_angular_tolerance = 0.22

        highlight_list = [tag for tag in (highlight_tags or [])]
        labels = tag_labels or {}
        label_points: Dict[str, Tuple[float, float, float]] = {}

        all_polys: List[List[Tuple[float, float, float]]] = []
        all_colors: List[Tuple[float, float, float, float]] = []
        triangles: List[np.ndarray] = []
        tri_normals: List[np.ndarray] = []
        bbox_min = np.array([np.inf, np.inf, np.inf])
        bbox_max = np.array([-np.inf, -np.inf, -np.inf])

        base_rgb = np.array(to_rgb(base_color))
        palette = [
            "#f39c12",
            "#9b59b6",
            "#f1c40f",
            "#1abc9c",
            "#e67e22",
            "#e84393",
            "#16a085",
            "#d35400",
        ]
        highlight_colors = highlight_colors or {}
        highlight_color_map: Dict[str, np.ndarray] = {}
        for idx, tag in enumerate(highlight_list):
            if tag in highlight_colors:
                highlight_color_map[tag] = np.array(to_rgb(highlight_colors[tag]))
            else:
                highlight_color_map[tag] = np.array(to_rgb(palette[idx % len(palette)]))

        light_dirs = [
            np.array([0.7, -0.1, 0.7]),
            np.array([-0.6, 0.25, 0.32]),
            np.array([0.15, -0.9, 0.2]),
            np.array([0.0, 0.0, 1.0]),
            np.array([-0.15, -0.1, -0.98]),
        ]
        light_dirs = [vec / np.linalg.norm(vec) for vec in light_dirs]
        light_weights = [1.35, 0.4, 0.3, 0.18, 0.08]

        def _shade(normals: np.ndarray, color: np.ndarray) -> np.ndarray:
            ambient = 0.12
            intensity = np.full((normals.shape[0],), ambient, dtype=float)
            for w, light in zip(light_weights, light_dirs):
                intensity += w * np.maximum(0.0, normals @ light)
            intensity = np.clip(intensity, 0.0, 1.0)
            intensity = np.power(intensity, 1.35)
            shaded = color[None, :] * intensity[:, None]
            shaded = np.clip(shaded, 0.0, 1.0)
            alpha = np.ones((shaded.shape[0], 1))
            return np.hstack([shaded, alpha])

        for solid in solids:
            bb = bounding_box(solid.wrapped)
            bbox_min = np.minimum(bbox_min, np.array([bb.xmin, bb.ymin, bb.zmin]))
            bbox_max = np.maximum(bbox_max, np.array([bb.xmax, bb.ymax, bb.zmax]))

        model_min = bbox_min.copy()
        model_max = bbox_max.copy()

        axis_solids: List[Solid] = []
        axis_colors: Dict[str, np.ndarray] = {}
        axis_len_x = 0.0
        axis_len_y = 0.0
        axis_len_z = 0.0
        if show_axes:
            span = float(np.max(model_max - model_min))
            if span <= 0:
                span = 1.0
            axis_margin = span * 0.08
            axis_len_x_base = max(span * 0.3, max(0.0, bbox_max[0]) + axis_margin)
            axis_len_y_base = max(span * 0.3, max(0.0, bbox_max[1]) + axis_margin)
            axis_len_z_base = max(span * 0.3, max(0.0, bbox_max[2]) + axis_margin)
            axis_len_x = max(0.0, axis_len_x_base + axis_margin * (axis_scale - 1.0))
            axis_len_y = max(0.0, axis_len_y_base + axis_margin * (axis_scale - 1.0))
            axis_len_z = max(0.0, axis_len_z_base + axis_margin * (axis_scale - 1.0))
            axis_radius = max(
                span * 0.004, min(axis_len_x, axis_len_y, axis_len_z) * 0.02
            )
            head_len_factor = 0.2
            head_radius = axis_radius * 2.0

            def _axis_solid(axis: Tuple[float, float, float], length: float) -> Solid:
                shaft_len = length * (1.0 - head_len_factor)
                head_len = length * head_len_factor
                shaft = make_cylinder_rsolid(
                    axis_radius,
                    shaft_len,
                    bottom_face_center=(0.0, 0.0, 0.0),
                    axis=axis,
                )
                cone = make_cone_rsolid(
                    head_radius,
                    head_len,
                    0.0,
                    bottom_face_center=tuple(np.array(axis) * shaft_len),
                    axis=axis,
                )
                merged = union_rsolid(shaft, cone)
                return merged

            axis_x = _axis_solid((1.0, 0.0, 0.0), axis_len_x)
            axis_y = _axis_solid((0.0, 1.0, 0.0), axis_len_y)
            axis_z = _axis_solid((0.0, 0.0, 1.0), axis_len_z)

            axis_x._apply_tag("axis.x")
            axis_y._apply_tag("axis.y")
            axis_z._apply_tag("axis.z")
            axis_solids = [axis_x, axis_y, axis_z]
            axis_colors = {
                "axis.x": np.array([1.0, 0.35, 0.35]),
                "axis.y": np.array([0.35, 1.0, 0.55]),
                "axis.z": np.array([0.45, 0.65, 1.0]),
            }

        render_solids = solids + axis_solids

        for solid in render_solids:
            bb = bounding_box(solid.wrapped)
            if solid not in solids and fit_mode == "axes":
                bbox_min = np.minimum(bbox_min, np.array([bb.xmin, bb.ymin, bb.zmin]))
                bbox_max = np.maximum(bbox_max, np.array([bb.xmax, bb.ymax, bb.zmax]))

            highlight_tag = next(
                (tag for tag in highlight_list if solid._has_tag(tag)), None
            )
            axis_tag = next((tag for tag in axis_colors if solid._has_tag(tag)), None)
            if highlight_tag and highlight_tag not in label_points:
                label_points[highlight_tag] = (
                    0.5 * (bb.xmin + bb.xmax),
                    0.5 * (bb.ymin + bb.ymax),
                    0.5 * (bb.zmin + bb.zmax),
                )

            for face in solid.get_faces():
                face_tag = next(
                    (tag for tag in highlight_list if face._has_tag(tag)), None
                )
                face_highlight_tag = face_tag or highlight_tag
                if face_highlight_tag and face_tag and face_tag not in label_points:
                    center = face.get_center()
                    label_points[face_tag] = (center.x, center.y, center.z)

                verts, tri_indices = tessellate_face(
                    face.wrapped, mesh_tolerance, mesh_angular_tolerance
                )
                if not tri_indices:
                    continue

                vertices = np.array(verts, dtype=float)
                tris = np.array(tri_indices, dtype=int)
                tri_pts = vertices[tris]
                normals = np.cross(
                    tri_pts[:, 1] - tri_pts[:, 0], tri_pts[:, 2] - tri_pts[:, 0]
                )
                norms = np.linalg.norm(normals, axis=1)
                normals = np.divide(
                    normals,
                    norms[:, None],
                    out=np.zeros_like(normals),
                    where=norms[:, None] != 0,
                )

                if axis_tag:
                    color = axis_colors[axis_tag]
                elif face_highlight_tag:
                    color = highlight_color_map.get(face_highlight_tag, base_rgb)
                else:
                    color = base_rgb
                colors = _shade(normals, color)
                all_polys.extend(tri_pts.tolist())
                all_colors.extend(colors.tolist())
                triangles.extend(list(tri_pts))
                tri_normals.extend(list(normals))

        if not all_polys:
            raise ValueError("未生成任何可渲染三角面")

        fig = plt.figure(figsize=(image_size[0] / 100, image_size[1] / 100), dpi=100)
        fig.patch.set_facecolor(background)
        ax = fig.add_subplot(111, projection="3d")
        ax.set_facecolor(background)
        ax.set_axis_off()
        fig.subplots_adjust(left=0.0, right=1.0, bottom=0.0, top=1.0)
        ax.set_position((0.0, 0.0, 1.0, 1.0))

        if wireframe_only:
            face_colors = np.array(all_colors, dtype=float)
            face_colors[:, 3] = 0.0
            collection = Poly3DCollection(
                all_polys, facecolors=face_colors, linewidths=0.0
            )
        else:
            collection = Poly3DCollection(
                all_polys, facecolors=all_colors, linewidths=0.0
            )
        collection.set_edgecolor((0, 0, 0, 0))
        collection.set_zsort("average")
        ax.add_collection3d(collection)

        bbox_min = model_min
        bbox_max = model_max
        axis_origin = np.array([0.0, 0.0, 0.0])
        if show_axes:
            axis_points = np.array(
                [
                    axis_origin,
                    axis_origin + np.array([axis_len_x, 0.0, 0.0]),
                    axis_origin + np.array([0.0, axis_len_y, 0.0]),
                    axis_origin + np.array([0.0, 0.0, axis_len_z]),
                ]
            )
        else:
            axis_points = np.array([axis_origin])

        extent_min = model_min.copy()
        extent_max = model_max.copy()
        if fit_mode == "axes":
            extent_min = np.minimum(extent_min, axis_points.min(axis=0))
            extent_max = np.maximum(extent_max, axis_points.max(axis=0))
        elif fit_mode == "model":
            weight = float(axis_fit_weight)
            if weight > 0 and show_axes:
                weight = max(0.0, min(1.0, weight))
                axis_min = axis_points.min(axis=0)
                axis_max = axis_points.max(axis=0)
                extent_min = np.where(
                    axis_min < extent_min,
                    extent_min + (axis_min - extent_min) * weight,
                    extent_min,
                )
                extent_max = np.where(
                    axis_max > extent_max,
                    extent_max + (axis_max - extent_max) * weight,
                    extent_max,
                )
        else:
            raise ValueError("fit_mode 仅支持 'model' 或 'axes'")

        span = float(np.max(extent_max - extent_min))
        if span <= 0:
            span = 1.0
        if zoom <= 0:
            raise ValueError("zoom 必须大于 0")
        size = extent_max - extent_min
        pad_ratio = 0.08
        pad_min = span * 0.01
        pad_vec = np.maximum(size * (pad_ratio / zoom), pad_min)
        min_extent = extent_min - pad_vec
        max_extent = extent_max + pad_vec
        ax.set_xlim(min_extent[0], max_extent[0])
        ax.set_ylim(min_extent[1], max_extent[1])
        ax.set_zlim(min_extent[2], max_extent[2])
        try:
            ax.set_box_aspect(max_extent - min_extent)
        except Exception:
            pass

        def _resolve_view(view_spec):
            if isinstance(view_spec, str):
                token = view_spec.strip().lower()
                spans = bbox_max - bbox_min
                if token == "auto":
                    azim = 35.0 if spans[0] >= spans[1] else 125.0
                    elev = 22.0 if spans[2] <= max(spans[0], spans[1]) else 35.0
                    return elev, azim
                if token in {"iso", "isometric"}:
                    return 25.0, 35.0
                if token == "top":
                    return 90.0, 0.0
                if token == "bottom":
                    return -90.0, 0.0
                if token == "front":
                    return 0.0, -90.0
                if token == "back":
                    return 0.0, 90.0
                if token == "left":
                    return 0.0, 180.0
                if token == "right":
                    return 0.0, 0.0
                if token == "front_right":
                    return 20.0, -45.0
                if token == "front_left":
                    return 20.0, 135.0
                if token == "rear_right":
                    return 20.0, 45.0
                if token == "rear_left":
                    return 20.0, -135.0
                raise ValueError(f"不支持的 view 预设: {view_spec}")

            if isinstance(view_spec, (list, tuple)) and len(view_spec) == 2:
                return float(view_spec[0]), float(view_spec[1])

            raise ValueError("view 必须为 (elev, azim) 或预设名称")

        elev, azim = _resolve_view(view)
        ax.view_init(elev=elev, azim=azim)

        if triangles:
            elev_rad = math.radians(elev)
            azim_rad = math.radians(azim)
            view_dir = np.array(
                [
                    math.cos(elev_rad) * math.cos(azim_rad),
                    math.cos(elev_rad) * math.sin(azim_rad),
                    math.sin(elev_rad),
                ],
                dtype=float,
            )
            edge_quant = max(mesh_tolerance * 0.001, 1e-6)

            def _quantize_point(point: np.ndarray) -> Tuple[float, float, float]:
                snapped = np.round(point / edge_quant) * edge_quant
                return (float(snapped[0]), float(snapped[1]), float(snapped[2]))

            edge_to_tris: Dict[
                Tuple[Tuple[float, float, float], Tuple[float, float, float]],
                List[int],
            ] = {}
            edge_to_seg: Dict[
                Tuple[Tuple[float, float, float], Tuple[float, float, float]],
                Tuple[np.ndarray, np.ndarray],
            ] = {}

            for tri_idx, tri in enumerate(triangles):
                for i0, i1 in ((0, 1), (1, 2), (2, 0)):
                    p0 = tri[i0]
                    p1 = tri[i1]
                    q0 = _quantize_point(p0)
                    q1 = _quantize_point(p1)
                    key = (q0, q1) if q0 <= q1 else (q1, q0)
                    edge_to_tris.setdefault(key, []).append(tri_idx)
                    edge_to_seg.setdefault(key, (p0, p1))

            hard_segments: List[np.ndarray] = []
            silhouette_segments: List[np.ndarray] = []
            angle_threshold = max(math.radians(40.0), mesh_angular_tolerance * 3.0)

            for key, tri_indices in edge_to_tris.items():
                seg = edge_to_seg[key]
                if len(tri_indices) == 1:
                    silhouette_segments.append(np.array(seg, dtype=float))
                    continue

                normals = [tri_normals[i] for i in tri_indices]
                facing = [float(np.dot(n, view_dir)) for n in normals]
                if min(facing) <= 0.0 <= max(facing):
                    silhouette_segments.append(np.array(seg, dtype=float))

                max_angle = 0.0
                for i in range(len(normals)):
                    for j in range(i + 1, len(normals)):
                        dot = float(np.clip(np.dot(normals[i], normals[j]), -1.0, 1.0))
                        angle = math.acos(dot)
                        if angle > max_angle:
                            max_angle = angle
                if max_angle >= angle_threshold:
                    hard_segments.append(np.array(seg, dtype=float))

            if hard_segments:
                hard_collection = Line3DCollection(
                    hard_segments,
                    colors=[(0.62, 0.64, 0.68, 0.75)],
                    linewidths=0.6,
                )
                ax.add_collection3d(hard_collection)
            if silhouette_segments:
                sil_collection = Line3DCollection(
                    silhouette_segments,
                    colors=[(0.88, 0.89, 0.92, 0.9)],
                    linewidths=1.1,
                )
                ax.add_collection3d(sil_collection)

        def _project_to_fig(point: Tuple[float, float, float]) -> Tuple[float, float]:
            x2, y2, _ = proj3d.proj_transform(
                point[0], point[1], point[2], ax.get_proj()
            )
            display = ax.transData.transform((x2, y2))
            return tuple(fig.transFigure.inverted().transform(display))

        def _clamp(value: float, low: float, high: float) -> float:
            return max(low, min(high, value))

        if show_axes:
            axis_label_offset = 0.008
            axis_label_specs = (
                ("X", axis_origin + np.array([axis_len_x, 0.0, 0.0]), "axis.x"),
                ("Y", axis_origin + np.array([0.0, axis_len_y, 0.0]), "axis.y"),
                ("Z", axis_origin + np.array([0.0, 0.0, axis_len_z]), "axis.z"),
            )
            for label, point, tag in axis_label_specs:
                color = axis_colors.get(tag, np.array([1.0, 1.0, 1.0]))
                xfig, yfig = _project_to_fig(
                    (float(point[0]), float(point[1]), float(point[2]))
                )
                xfig = _clamp(xfig + axis_label_offset, 0.02, 0.98)
                yfig = _clamp(yfig + axis_label_offset, 0.02, 0.98)
                fig.text(
                    xfig,
                    yfig,
                    label,
                    color=color,
                    fontsize=16,
                    ha="left",
                    va="center",
                )

        if show_legend and (highlight_list or show_axes):
            y = 0.98
            if highlight_list:
                for tag in highlight_list:
                    label = labels.get(tag, tag)
                    color = highlight_color_map.get(tag, base_rgb)
                    fig.text(
                        0.02,
                        y,
                        f"■ {label}",
                        color=color,
                        fontsize=10,
                        ha="left",
                        va="top",
                    )
                    y -= 0.035

            if show_axes:
                for label, color in (
                    ("+X", axis_colors.get("axis.x", np.array([1.0, 0.35, 0.35]))),
                    ("+Y", axis_colors.get("axis.y", np.array([0.35, 1.0, 0.55]))),
                    ("+Z", axis_colors.get("axis.z", np.array([0.45, 0.65, 1.0]))),
                ):
                    fig.text(
                        0.02,
                        y,
                        f"■ {label}",
                        color=color,
                        fontsize=10,
                        ha="left",
                        va="top",
                    )
                    y -= 0.035

        if show_callouts:
            label_offset = 0.012
            for idx, (tag, point) in enumerate(label_points.items()):
                label = labels.get(tag, tag)
                xfig, yfig = _project_to_fig(point)
                xfig = _clamp(xfig + label_offset, 0.02, 0.98)
                yfig = _clamp(yfig + label_offset, 0.02, 0.98)
                yfig = _clamp(yfig - idx * 0.02, 0.02, 0.98)
                fig.text(
                    xfig,
                    yfig,
                    label,
                    color="#ffd27a",
                    fontsize=10,
                    ha="left",
                    va="center",
                    bbox=dict(
                        boxstyle="round,pad=0.2",
                        fc="#111111",
                        ec="#ffaa33",
                        alpha=0.9,
                    ),
                )

        plt.savefig(output_path, facecolor=background)
        plt.close(fig)
        return output_path
    except Exception as e:
        _wrap_public_api_error(
            operation="render_screenshot_rpath",
            what_happened="Failed to render the screenshot.",
            possible_causes=[
                "The input does not contain any valid Solid objects.",
                "The rendering view or zoom configuration is invalid.",
                "The output path is invalid or not writable.",
            ],
            how_to_fix=[
                "Pass a Solid or a sequence of Solid objects.",
                "Use a supported view preset or a valid (elev, azim) tuple.",
                "Check that the output path is writable.",
            ],
            error=e,
        )


# =============================================================================
# 高级特征操作函数
# =============================================================================


def fillet_rsolid(
    solid: Solid,
    edges: Union[Sequence[Edge], ShapeSelector],
    radius: ScalarLike,
    *,
    output_tags: Optional[Mapping[str, str]] = None,
    result_tag: Optional[str] = None,
    generated_faces_tag: Optional[str] = None,
) -> Solid:
    """Apply fillets, with optional tagging of kernel-proven patch faces."""
    try:
        assignments = _normalize_operation_output_tags(
            _OP_MAKE_FILLET_RSOLID,
            output_tags,
            (("fillet.patch", generated_faces_tag),),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        radius_value = evaluate_scalar(radius)
        if radius_value <= 0:
            raise ValueError("圆角半径必须大于0")

        selected_edges = cast(List[Edge], _resolve_selector_or_shapes(solid, edges))
        if not selected_edges:
            raise ValueError("圆角操作至少需要一条边")

        tracked = tracked_fillet(solid, selected_edges, radius_value)
        result = cast(Solid, tracked.shape)

        result._metadata = solid._metadata.copy()

        selected_edge_refs = _serialize_shape_refs(selected_edges)
        selected_edge_node_ids = _ensure_geo_selection_node_ids(solid, selected_edges)

        selection_params: Dict[str, object] = {
            "radius": radius,
            "edge_count": len(selected_edges),
            "selected_edges": selected_edge_refs,
        }
        if selected_edge_node_ids:
            selection_params["selected_edge_node_ids"] = selected_edge_node_ids
        else:
            selection_params["selected_edge_indices"] = _serialize_selection_indices(
                selected_edges, solid.get_edges()
            )

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            result,
            op=_OP_MAKE_FILLET_RSOLID,
            params=selection_params,
            source_solid=solid,
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[solid, *selected_edges],
        )
        return _apply_operation_output_tags(
            finalized,
            op=_OP_MAKE_FILLET_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="fillet_rsolid",
            what_happened="Failed to apply the fillet operation.",
            possible_causes=[
                "The radius is not a positive finite scalar.",
                "No valid edges were selected.",
                "The selected edges are incompatible with the requested fillet radius.",
            ],
            how_to_fix=[
                "Use a positive fillet radius.",
                "Select at least one valid edge or use a selector that resolves to edges.",
                "If the kernel rejects the fillet, try a smaller radius or a simpler edge set.",
            ],
            error=e,
        )


def chamfer_rsolid(
    solid: Solid,
    edges: Union[Sequence[Edge], ShapeSelector],
    distance: ScalarLike,
    *,
    output_tags: Optional[Mapping[str, str]] = None,
    result_tag: Optional[str] = None,
    generated_faces_tag: Optional[str] = None,
) -> Solid:
    """Apply chamfers, with optional tagging of kernel-proven patch faces."""
    try:
        assignments = _normalize_operation_output_tags(
            _OP_MAKE_CHAMFER_RSOLID,
            output_tags,
            (("chamfer.patch", generated_faces_tag),),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        distance_value = evaluate_scalar(distance)
        if distance_value <= 0:
            raise ValueError("倒角距离必须大于0")

        selected_edges = cast(List[Edge], _resolve_selector_or_shapes(solid, edges))
        if not selected_edges:
            raise ValueError("倒角操作至少需要一条边")

        tracked = tracked_chamfer(solid, selected_edges, distance_value)
        result = cast(Solid, tracked.shape)

        result._metadata = solid._metadata.copy()

        selected_edge_refs = _serialize_shape_refs(selected_edges)
        selected_edge_node_ids = _ensure_geo_selection_node_ids(solid, selected_edges)

        selection_params: Dict[str, object] = {
            "distance": distance,
            "edge_count": len(selected_edges),
            "selected_edges": selected_edge_refs,
        }
        if selected_edge_node_ids:
            selection_params["selected_edge_node_ids"] = selected_edge_node_ids
        else:
            selection_params["selected_edge_indices"] = _serialize_selection_indices(
                selected_edges, solid.get_edges()
            )

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            result,
            op=_OP_MAKE_CHAMFER_RSOLID,
            params=selection_params,
            source_solid=solid,
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[solid, *selected_edges],
        )
        return _apply_operation_output_tags(
            finalized,
            op=_OP_MAKE_CHAMFER_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="chamfer_rsolid",
            what_happened="Failed to apply the chamfer operation.",
            possible_causes=[
                "The distance is not a positive finite scalar.",
                "No valid edges were selected.",
                "The selected edges are incompatible with the requested chamfer size.",
            ],
            how_to_fix=[
                "Use a positive chamfer distance.",
                "Select at least one valid edge or use a selector that resolves to edges.",
                "If the kernel rejects the chamfer, try a smaller distance or fewer edges.",
            ],
            error=e,
        )


def shell_rsolid(
    solid: Solid,
    faces_to_remove: Union[Sequence[Face], ShapeSelector],
    thickness: ScalarLike,
    *,
    output_tags: Optional[Mapping[str, str]] = None,
    result_tag: Optional[str] = None,
    body_faces_tag: Optional[str] = None,
    offset_faces_tag: Optional[str] = None,
    closing_faces_tag: Optional[str] = None,
    wall_edges_tag: Optional[str] = None,
) -> Solid:
    """Shell a solid, with optional kernel-role-based face tags."""
    try:
        assignments = _normalize_operation_output_tags(
            _OP_MAKE_SHELL_RSOLID,
            output_tags,
            (
                ("shell.body_face", body_faces_tag),
                ("shell.offset_face", offset_faces_tag),
                ("shell.closing_descendant", closing_faces_tag),
                ("shell.wall", wall_edges_tag),
            ),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        thickness_value = evaluate_scalar(thickness)
        if thickness_value <= 0:
            raise ValueError("壁厚必须大于0")

        selected_faces = cast(
            List[Face], _resolve_selector_or_shapes(solid, faces_to_remove)
        )
        if not selected_faces:
            raise ValueError("抽壳操作至少需要一个待移除面")

        # 转换为 OCP 面对象
        tracked = tracked_shell(solid, selected_faces, thickness_value)
        result = cast(Solid, tracked.shape)

        result._metadata = solid._metadata.copy()

        selected_face_refs = _serialize_shape_refs(selected_faces)
        selected_face_node_ids = _ensure_geo_selection_node_ids(solid, selected_faces)

        selection_params: Dict[str, object] = {
            "thickness": thickness,
            "removed_face_count": len(selected_faces),
            "selected_faces": selected_face_refs,
        }
        if selected_face_node_ids:
            selection_params["selected_face_node_ids"] = selected_face_node_ids
        else:
            selection_params["selected_face_indices"] = _serialize_selection_indices(
                selected_faces, solid.get_faces()
            )

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            result,
            op=_OP_MAKE_SHELL_RSOLID,
            params=selection_params,
            source_solid=solid,
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[solid, *selected_faces],
        )
        return _apply_operation_output_tags(
            finalized,
            op=_OP_MAKE_SHELL_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="shell_rsolid",
            what_happened="Failed to apply the shell operation.",
            possible_causes=[
                "The thickness is not a positive finite scalar.",
                "No valid faces were selected for removal.",
                "The requested shell thickness is incompatible with the current solid.",
            ],
            how_to_fix=[
                "Use a positive shell thickness.",
                "Select at least one valid face to remove.",
                "If the shell fails, try a smaller thickness or a different face selection.",
            ],
            error=e,
        )


def loft_rsolid(
    profiles: List[Wire],
    ruled: bool = False,
    *,
    output_tags: Optional[Mapping[str, str]] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid:
    """Create a lofted solid, with optional kernel-role-based tags."""
    try:
        assignments = _normalize_operation_output_tags(
            _OP_MAKE_LOFT_RSOLID,
            output_tags,
            (
                ("loft.start", start_face_tag),
                ("loft.end", end_face_tag),
                ("loft.side", side_faces_tag),
            ),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        if len(profiles) < 2:
            raise ValueError("放样至少需要2个轮廓")

        tracked = tracked_loft(profiles, ruled=ruled)
        result = cast(Solid, tracked.shape)

        all_metadata = {}
        for profile in profiles:
            all_metadata.update(profile._metadata)

        result._metadata = all_metadata

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            result,
            op=_OP_MAKE_LOFT_RSOLID,
            params={"profile_count": len(profiles), "ruled": ruled},
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=profiles,
        )
        return _apply_operation_output_tags(
            finalized,
            op=_OP_MAKE_LOFT_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="loft_rsolid",
            what_happened="Failed to loft the input profiles into a solid.",
            possible_causes=[
                "Fewer than two profiles were provided.",
                "One or more profiles are invalid or incompatible.",
                "The kernel rejected the loft because the section geometry is inconsistent.",
            ],
            how_to_fix=[
                "Pass at least two valid Wire profiles.",
                "Keep the profile topology compatible across sections.",
                "If loft fails, inspect each profile individually and simplify the section geometry.",
            ],
            error=e,
        )


def sweep_rsolid(
    profile: Face,
    path: Wire,
    is_frenet: bool = False,
    *,
    output_tags: Optional[Mapping[str, str]] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_faces_tag: Optional[str] = None,
) -> Solid:
    """Create a swept solid, with optional kernel-role-based tags."""
    make_solid = True  # 默认创建实体
    try:
        assignments = _normalize_operation_output_tags(
            _OP_MAKE_SWEEP_RSOLID,
            output_tags,
            (
                ("sweep.start", start_face_tag),
                ("sweep.end", end_face_tag),
                ("sweep.side", side_faces_tag),
            ),
        )
        normalized_result_tag = (
            normalize_tag(result_tag, strict=True) if result_tag is not None else None
        )
        tracked = tracked_sweep(profile, path, is_frenet=is_frenet)
        result = cast(Solid, tracked.shape)

        result._metadata = {**profile._metadata, **path._metadata}

        target_kinds = _validate_operation_output_roles(tracked.delta, assignments)
        finalized = _finalize_tracked_solid(
            result,
            op=_OP_MAKE_SWEEP_RSOLID,
            params={"is_frenet": bool(is_frenet)},
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[profile, path],
        )
        return _apply_operation_output_tags(
            finalized,
            op=_OP_MAKE_SWEEP_RSOLID,
            assignments=assignments,
            target_kinds=target_kinds,
            result_tag=normalized_result_tag,
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="sweep_rsolid",
            what_happened="Failed to sweep the profile along the path.",
            possible_causes=[
                "The profile face is invalid.",
                "The path wire is invalid or unsuitable for sweep.",
                "The kernel rejected the sweep orientation or geometry.",
            ],
            how_to_fix=[
                "Pass a valid Face profile and a valid Wire path.",
                "Check that the path wire is continuous and geometrically reasonable.",
                "If sweep fails, simplify the profile or path before retrying.",
            ],
            error=e,
        )


def linear_pattern_rsolidlist(
    shape: AnyShape, direction: Tuple[float, float, float], count: int, spacing: float
) -> List[Solid]:
    """Create a linear pattern of solids."""
    try:
        if count <= 0:
            raise ValueError("阵列数量必须大于0")
        if spacing <= 0:
            raise ValueError("阵列间距必须大于0")

        cs = get_current_cs()
        global_direction = cs.transform_point(np.array(direction)) - cs.origin
        direction_norm = float(np.linalg.norm(global_direction))
        if direction_norm <= 1e-15:
            raise ValueError("阵列方向不能是零向量")
        direction_vec = global_direction / direction_norm

        if get_active_session() is not None:
            rv: List[Solid] = []
            for i in range(count):
                offset = direction_vec * (spacing * i)
                translated_shape = translate_shape(
                    shape, (float(offset[0]), float(offset[1]), float(offset[2]))
                )
                translated_shape._apply_tag("solid.pattern.linear", propagate=False)
                geo = dict(translated_shape.get_metadata("geo", {}))
                geo["pattern"] = {"type": "linear", "index": i + 1}
                translated_shape.set_metadata("geo", geo)
                _attach_track_summary(translated_shape, op="linear_pattern")
                rv.append(cast(Solid, translated_shape))
            return rv

        shapes = []
        with suspend_graph_recording():
            for i in range(count):
                offset = direction_vec * (spacing * i)
                translated_shape = translate_shape(
                    shape, (float(offset[0]), float(offset[1]), float(offset[2]))
                )
                shapes.append(translated_shape)

        rv = []
        for i, s in enumerate(shapes):
            s._apply_tag("solid.pattern.linear", propagate=False)
            geo = dict(s.get_metadata("geo", {}))
            geo["pattern"] = {"type": "linear", "index": i + 1}
            s.set_metadata("geo", geo)
            _attach_track_summary(s, op="linear_pattern")
            rv.append(s)

        record_operation_if_active(
            op="linear_pattern",
            params={
                "direction": direction,
                "count": count,
                "spacing": spacing,
            },
            outputs=rv,
            input_shapes=[shape],
            context=_current_context_metadata(),
        )

        return rv

    except Exception as e:
        _wrap_public_api_error(
            operation="linear_pattern_rsolidlist",
            what_happened="Failed to create the linear pattern.",
            possible_causes=[
                "The count is not a positive integer.",
                "The spacing is not positive.",
                "The direction vector is invalid.",
            ],
            how_to_fix=[
                "Use count >= 1.",
                "Use spacing > 0.",
                "Pass a valid finite direction vector.",
            ],
            error=e,
        )


def radial_pattern_rsolidlist(
    shape: AnyShape,
    center: Tuple[float, float, float],
    axis: Tuple[float, float, float],
    count: int,
    total_rotation_angle: float,
) -> List[Solid]:
    """Create a radial pattern of solids."""
    try:
        if count <= 0:
            raise ValueError("阵列数量必须大于0")
        if total_rotation_angle <= 0:
            raise ValueError("角度必须大于0")

        shapes = []
        angle_step = total_rotation_angle / count  # 修正角度计算，均匀分布

        if get_active_session() is not None:
            rv: List[Solid] = []
            for i in range(count):
                rotation_angle = angle_step * i
                rotated_shape = (
                    cast(Solid, translate_shape(shape, (0.0, 0.0, 0.0)))
                    if i == 0
                    else cast(Solid, rotate_shape(shape, rotation_angle, axis, center))
                )
                rotated_shape._apply_tag("solid.pattern.radial", propagate=False)
                geo = dict(rotated_shape.get_metadata("geo", {}))
                geo["pattern"] = {"type": "radial", "index": i + 1}
                rotated_shape.set_metadata("geo", geo)
                _attach_track_summary(rotated_shape, op="radial_pattern")
                rv.append(cast(Solid, rotated_shape))
            return rv

        with suspend_graph_recording():
            for i in range(count):
                rotation_angle = angle_step * i
                rotated_shape = rotate_shape(shape, rotation_angle, axis, center)
                shapes.append(rotated_shape)

        rv = []
        for i, s in enumerate(shapes):
            s._apply_tag("solid.pattern.radial", propagate=False)
            geo = dict(s.get_metadata("geo", {}))
            geo["pattern"] = {"type": "radial", "index": i + 1}
            s.set_metadata("geo", geo)
            _attach_track_summary(s, op="radial_pattern")
            rv.append(s)

        record_operation_if_active(
            op="radial_pattern",
            params={
                "center": center,
                "axis": axis,
                "count": count,
                "total_rotation_angle": total_rotation_angle,
            },
            outputs=rv,
            input_shapes=[shape],
            context=_current_context_metadata(),
        )

        return rv
    except Exception as e:
        _wrap_public_api_error(
            operation="radial_pattern_rsolidlist",
            what_happened="Failed to create the radial pattern.",
            possible_causes=[
                "The count is not a positive integer.",
                "The total rotation angle is not positive.",
                "The center or axis is invalid.",
            ],
            how_to_fix=[
                "Use count >= 1.",
                "Use a total rotation angle greater than zero.",
                "Pass a valid center point and a non-zero axis vector.",
            ],
            error=e,
        )


def mirror_shape(
    shape: AnyShape,
    plane_origin: Tuple[float, float, float],
    plane_normal: Tuple[float, float, float],
) -> AnyShape:
    """Mirror a shape across a plane."""
    try:
        cs = get_current_cs()
        plane_origin_value = cast(
            Tuple[float, float, float], evaluate_value(plane_origin)
        )
        plane_normal_value = cast(
            Tuple[float, float, float], evaluate_value(plane_normal)
        )
        global_origin = cs.transform_point(np.array(plane_origin_value))
        global_normal = cs.transform_vector(np.array(plane_normal_value))

        # 确保法向量不是零向量
        if np.linalg.norm(global_normal) < 1e-10:
            raise ValueError("镜像平面法向量不能是零向量")

        if isinstance(shape, Solid):
            tracked = tracked_mirror(
                shape,
                (
                    float(global_origin[0]),
                    float(global_origin[1]),
                    float(global_origin[2]),
                ),
                (
                    float(global_normal[0]),
                    float(global_normal[1]),
                    float(global_normal[2]),
                ),
            )
            new_shape = cast(Solid, tracked.shape)
            new_shape._metadata = shape._metadata.copy()
            _attach_lineage_from_source(
                shape,
                new_shape,
                derivation="continuation",
                op=_OP_MAKE_MIRROR_RSHAPE,
            )
            new_shape._apply_tag("solid.transform.mirrored", propagate=False)
            return _finalize_tracked_solid(
                new_shape,
                op=_OP_MAKE_MIRROR_RSHAPE,
                params={
                    "plane_origin": plane_origin,
                    "plane_normal": plane_normal,
                },
                source_solid=shape,
                delta=tracked.delta,
                delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
                input_shapes=[shape],
            )

        else:
            new_shape = mirror_shape_ocp(
                shape,
                (
                    float(global_origin[0]),
                    float(global_origin[1]),
                    float(global_origin[2]),
                ),
                (
                    float(global_normal[0]),
                    float(global_normal[1]),
                    float(global_normal[2]),
                ),
            )

        new_shape._metadata = shape._metadata.copy()
        _attach_lineage_from_source(
            shape,
            new_shape,
            derivation="continuation",
            op=_OP_MAKE_MIRROR_RSHAPE,
        )
        new_shape._apply_tag("solid.transform.mirrored", propagate=False)

        _attach_track_summary(new_shape, op=_OP_MAKE_MIRROR_RSHAPE)
        record_operation_if_active(
            op=_OP_MAKE_MIRROR_RSHAPE,
            params={
                "plane_origin": plane_origin,
                "plane_normal": plane_normal,
            },
            outputs=new_shape,
            input_shapes=[shape],
            context=_current_context_metadata(),
        )

        return new_shape
    except Exception as e:
        _wrap_public_api_error(
            operation="mirror_shape",
            what_happened="Failed to mirror the shape across the plane.",
            possible_causes=[
                "The plane origin or plane normal is invalid.",
                "The plane normal is zero-length.",
                "The kernel rejected the mirror transform.",
            ],
            how_to_fix=[
                "Pass a valid plane origin and a non-zero plane normal.",
                "Validate the shape before mirroring.",
                "If the plane is computed dynamically, inspect the evaluated values first.",
            ],
            error=e,
        )


def helical_sweep_rsolid(
    profile: Wire,
    pitch: float,
    height: float,
    radius: float,
    center: Tuple[float, float, float] = (0, 0, 0),
    dir: Tuple[float, float, float] = (0, 0, 1),
) -> Solid:
    """Create a solid by sweeping a profile along a helical path."""
    try:
        if get_active_session() is not None:
            helix = make_helix_rwire(pitch, height, radius, center=center, dir=dir)
            return sweep_rsolid(
                make_face_from_wire_rface(profile), helix, is_frenet=True
            )

        if pitch <= 0:
            raise ValueError("螺距必须大于0")
        if height <= 0:
            raise ValueError("高度必须大于0")
        if radius <= 0:
            raise ValueError("半径必须大于0")

        cs = get_current_cs()
        global_center = cs.transform_point(np.array(center))
        global_dir = cs.transform_point(np.array(dir)) - cs.origin

        result_shape = make_helical_sweep_solid(
            profile.wrapped,
            pitch,
            height,
            radius,
            global_center,
            global_dir,
        )
        result = Solid(result_shape)

        result._metadata = profile._metadata.copy()
        result._apply_tag("solid.feature.helical_sweep", propagate=False)

        return result
    except Exception as e:
        _wrap_public_api_error(
            operation="helical_sweep_rsolid",
            what_happened="Failed to create the helical sweep solid.",
            possible_causes=[
                "Pitch, height, or radius is not positive.",
                "The input profile wire is invalid or cannot form a face.",
                "The center or direction vector is invalid.",
                "The underlying helix or sweep construction failed.",
            ],
            how_to_fix=[
                "Use positive pitch, height, and radius values.",
                "Pass a valid profile wire that can be turned into a face.",
                "Validate the center and direction inputs before retrying.",
                "If the sweep still fails, try the explicit macro path: helix wire -> face from profile -> sweep.",
            ],
            error=e,
        )
