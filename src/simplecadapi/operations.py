"""SimpleCAD API operation implementations based on the README design."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union, cast
import math
import numpy as np

from ._vendor_warning_filters import suppress_vendor_deprecation_warnings
from .errors import SimpleCADError, raise_harness_error

suppress_vendor_deprecation_warnings()

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeVertex, BRepBuilderAPI_Sewing
from OCP.TopAbs import TopAbs_SHELL
from OCP.TopExp import TopExp_Explorer
from OCP.gp import gp_Pnt

from .core import (
    Vertex,
    Edge,
    Wire,
    Face,
    Solid,
    AnyShape,
    get_current_cs,
)
from .field import (
    ScalarField,
    bounds_rbbox,
    serialize_scalar_field,
    eval_rarray,
    make_box_rscalarfield,
    intersect_rscalarfield,
)
from .autotag import apply_tracking_tags_to_delta
from .expr import ScalarLike, evaluate_scalar, evaluate_value
from .graph import (
    get_active_session,
    record_operation_if_active,
    suspend_graph_recording,
)
from .ql import ShapeSelector
from .topology import (
    SemanticDelta,
    SemanticRef,
    TopoDelta,
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
    make_helical_sweep_solid,
    make_loft_solid,
    make_sweep_solid,
)
from .kernel.ocp_transforms import (
    mirror_shape_ocp,
    rotate_shape_ocp,
    translate_shape_ocp,
)
from .kernel.ocp_booleans import common_shapes, fuse_shapes, solids_of
from .kernel.ocp_export import export_step_shapes, export_stl_shape, make_compound
from .kernel.ocp_mesh import make_triangle_face, shell_is_closed, shell_metric, solid_from_shell, tessellate_face
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
_OP_MAKE_FIELD_SURFACE_RSOLID = "make_field_surface_rsolid"
_OP_MAKE_TRANSLATE_RSHAPE = "make_translate_rshape"
_OP_MAKE_ROTATE_RSHAPE = "make_rotate_rshape"
_OP_MAKE_MIRROR_RSHAPE = "make_mirror_rshape"
_OP_MAKE_EXTRUDE_RSOLID = "make_extrude_rsolid"
_OP_MAKE_REVOLVE_RSOLID = "make_revolve_rsolid"
_OP_MAKE_LOFT_RSOLID = "make_loft_rsolid"
_OP_MAKE_SWEEP_RSOLID = "make_sweep_rsolid"
_OP_MAKE_UNION_RSOLIDLIST = "make_union_rsolidlist"
_OP_MAKE_CUT_RSOLIDLIST = "make_cut_rsolidlist"
_OP_MAKE_INTERSECT_RSOLIDLIST = "make_intersect_rsolidlist"
_OP_MAKE_FILLET_RSOLID = "make_fillet_rsolid"
_OP_MAKE_CHAMFER_RSOLID = "make_chamfer_rsolid"
_OP_MAKE_SHELL_RSOLID = "make_shell_rsolid"


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


def _warn_if_union_results_remain_separated(
    results: Sequence[Solid], tol: Optional[float]
) -> None:
    """Print a clear stdout warning when union results remain separated beyond tol."""

    if len(results) < 2:
        return

    effective_tol = float(tol or 0.0)
    nearest_gap_above_tol: Optional[float] = None

    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            gap = float(ocp_distance(results[i].wrapped, results[j].wrapped))
            if gap > effective_tol:
                if nearest_gap_above_tol is None or gap < nearest_gap_above_tol:
                    nearest_gap_above_tol = gap

    if nearest_gap_above_tol is None:
        return

    if len(results) == 2:
        print(
            "[WARNING] union_rsolidlist returned 2 separated solids: the two objects do not touch, "
            f"and the gap between them is about {nearest_gap_above_tol:.6g}, which exceeds tol={effective_tol:.6g}. "
            "Please check the relationship between the two objects and decide whether to adjust them so they connect, "
            "or accept them as two separate solids."
        )
        return

    print(
        f"[WARNING] union_rsolidlist returned {len(results)} separated solids: "
        "at least one pair of objects does not touch, "
        f"and the smallest detected separation gap is about {nearest_gap_above_tol:.6g}, which exceeds tol={effective_tol:.6g}. "
        "Please check the relationship between these objects and decide whether to adjust them so they connect, "
        "or accept them as separate solids."
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


def _copy_runtime_state(source: AnyShape, target: AnyShape) -> AnyShape:
    runtime = getattr(source, "_runtime", None)
    if isinstance(runtime, dict):
        target._runtime = runtime.copy()
    return target


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
        "tags": sorted(shape.get_tags()),
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

    return hint


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


def _serialize_selection_query(
    selection: Union[Sequence[AnyShape], ShapeSelector],
) -> Optional[Dict[str, object]]:
    if isinstance(selection, ShapeSelector):
        return cast(Dict[str, object], selection.to_dict())
    return None


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
            _OP_MAKE_CUT_RSOLIDLIST,
            _OP_MAKE_UNION_RSOLIDLIST,
            _OP_MAKE_INTERSECT_RSOLIDLIST,
            _OP_MAKE_TRANSLATE_RSHAPE,
            _OP_MAKE_ROTATE_RSHAPE,
            _OP_MAKE_MIRROR_RSHAPE,
            _OP_MAKE_FIELD_SURFACE_RSOLID,
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
                _OP_MAKE_CUT_RSOLIDLIST,
                _OP_MAKE_UNION_RSOLIDLIST,
                _OP_MAKE_INTERSECT_RSOLIDLIST,
                _OP_MAKE_FIELD_SURFACE_RSOLID,
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
        input_shapes=input_shapes,
        semantic_delta=_semantic_delta_for_output(op),
        context=_current_context_metadata(),
        tags=tags,
    )
    return shape


def _finalize_tracked_solid(
    solid: Solid,
    *,
    op: str,
    params: Dict[str, object],
    source_solid: Optional[Solid] = None,
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
        input_shapes=input_shapes,
        semantic_delta=_semantic_delta_for_output(op),
        topo_delta=cast(Optional[TopoDelta], delta),
        context=_current_context_metadata(),
    )
    return solid


# =============================================================================
# 基础图形创建函数
# =============================================================================


def make_point_rvertex(x: ScalarLike, y: ScalarLike, z: ScalarLike) -> Vertex:
    """Create a point in 3D space and return it as a vertex."""
    try:
        cs = get_current_cs()
        point_value = cast(Tuple[float, float, float], evaluate_value((x, y, z)))
        global_point = cs.transform_point(np.array(point_value))
        vertex_shape = BRepBuilderAPI_MakeVertex(gp_Pnt(float(global_point[0]), float(global_point[1]), float(global_point[2]))).Vertex()
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
        face._tags = wire._tags.copy()
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
        wire_points = [(float(point[0]), float(point[1]), float(point[2])) for point in global_points]
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
        face._tags = wire._tags.copy()
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
            # CADQuery的Wire没有直接的reverse方法，我们需要重新构建
            # 简单的方法是使用makeFromWires的orientation参数
            # 或者我们接受当前面的方向，添加一个警告
            print(f"警告: 创建的面的法向量与期望方向相反 (点积: {dot_product:.3f})")

        # 复制标签和元数据
        face._tags = wire._tags.copy()
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


_TETRAHEDRA = (
    (0, 5, 1, 6),
    (0, 1, 2, 6),
    (0, 2, 3, 6),
    (0, 3, 7, 6),
    (0, 7, 4, 6),
    (0, 4, 5, 6),
)
_TETRA_EDGES = ((0, 1), (1, 2), (2, 0), (0, 3), (1, 3), (2, 3))
_TETRA_TRI_TABLE = (
    (),
    (0, 3, 2),
    (0, 1, 4),
    (1, 4, 2, 2, 4, 3),
    (1, 2, 5),
    (0, 3, 5, 0, 5, 1),
    (0, 2, 5, 0, 5, 4),
    (5, 4, 3),
    (3, 4, 5),
    (4, 5, 0, 5, 2, 0),
    (1, 5, 0, 5, 3, 0),
    (5, 2, 1),
    (3, 4, 2, 2, 4, 1),
    (4, 1, 0),
    (2, 3, 0),
    (),
)
_CUBE_OFFSETS = np.array(
    [
        [0, 0, 0],
        [1, 0, 0],
        [1, 1, 0],
        [0, 1, 0],
        [0, 0, 1],
        [1, 0, 1],
        [1, 1, 1],
        [0, 1, 1],
    ],
    dtype=float,
)


def _evaluate_field_values(
    field, xs: np.ndarray, ys: np.ndarray, zs: np.ndarray
) -> np.ndarray:
    if isinstance(field, ScalarField):
        return eval_rarray(field, xs, ys, zs)

    if callable(field):
        try:
            values = field(xs, ys, zs)
            values = np.asarray(values, dtype=float)
            if values.shape != xs.shape:
                raise ValueError("field 输出形状不匹配")
            return values
        except Exception:
            vectorized = np.vectorize(field)
            return vectorized(xs, ys, zs).astype(float)

    raise ValueError("field 必须是 ScalarField 或可调用对象")


def _marching_tetrahedra(
    xs: np.ndarray,
    ys: np.ndarray,
    zs: np.ndarray,
    values: np.ndarray,
    iso: float,
) -> List[List[Tuple[float, float, float]]]:
    triangles: List[List[Tuple[float, float, float]]] = []
    nx, ny, nz = values.shape
    for i in range(nx - 1):
        for j in range(ny - 1):
            for k in range(nz - 1):
                cube_vals = np.array(
                    [
                        values[i + int(o[0]), j + int(o[1]), k + int(o[2])]
                        for o in _CUBE_OFFSETS
                    ],
                    dtype=float,
                )
                cube_pos = np.array(
                    [
                        (xs[i + int(o[0])], ys[j + int(o[1])], zs[k + int(o[2])])
                        for o in _CUBE_OFFSETS
                    ],
                    dtype=float,
                )
                grad = np.array(
                    [
                        cube_vals[1] - cube_vals[0],
                        cube_vals[3] - cube_vals[0],
                        cube_vals[4] - cube_vals[0],
                    ],
                    dtype=float,
                )
                eps = 1e-9 * max(1.0, float(np.max(np.abs(cube_vals))))
                for tetra in _TETRAHEDRA:
                    idx = list(tetra)
                    tpos = cube_pos[idx]
                    tval = cube_vals[idx] - iso
                    tval = np.where(np.abs(tval) < eps, -eps, tval)
                    case_index = 0
                    for v_index, v_val in enumerate(tval):
                        if v_val < 0:
                            case_index |= 1 << v_index

                    table = _TETRA_TRI_TABLE[case_index]
                    if not table:
                        continue

                    edge_points: dict[int, np.ndarray] = {}
                    for edge_index in set(table):
                        a, b = _TETRA_EDGES[edge_index]
                        v0 = tval[a]
                        v1 = tval[b]
                        t = v0 / (v0 - v1)
                        edge_points[edge_index] = tpos[a] + t * (tpos[b] - tpos[a])

                    for tri_idx in range(0, len(table), 3):
                        p0 = edge_points[table[tri_idx]]
                        p1 = edge_points[table[tri_idx + 1]]
                        p2 = edge_points[table[tri_idx + 2]]
                        tri = [p0, p1, p2]
                        if np.linalg.norm(grad) > 1e-9:
                            normal = np.cross(p1 - p0, p2 - p0)
                            if float(np.dot(normal, grad)) < 0:
                                tri = [p0, p2, p1]
                        triangles.append([tuple(p.tolist()) for p in tri])
    return triangles


def make_field_surface_rsolid(
    field,
    bounds: Optional[
        Tuple[Tuple[float, float, float], Tuple[float, float, float]]
    ] = None,
    resolution: Tuple[int, int, int] = (24, 24, 24),
    iso: float = 0.0,
    cap_bounds: bool = True,
) -> Solid:
    """Build a closed solid from a scalar field isosurface."""
    try:
        original_field = field
        if bounds is None:
            if isinstance(field, ScalarField):
                bounds = bounds_rbbox(field)
            else:
                raise ValueError("bounds 不能为空")

        (xmin, ymin, zmin), (xmax, ymax, zmax) = bounds
        if cap_bounds:
            center = ((xmin + xmax) / 2.0, (ymin + ymax) / 2.0, (zmin + zmax) / 2.0)
            size = (xmax - xmin, ymax - ymin, zmax - zmin)
            if isinstance(field, ScalarField):
                box_field = make_box_rscalarfield(center, size)
                field = intersect_rscalarfield(field, box_field)
            else:
                field_fn = field
                cx, cy, cz = center
                sx, sy, sz = size

                def box_eval(x, y, z):
                    dx = np.abs(x - cx) - sx / 2.0
                    dy = np.abs(y - cy) - sy / 2.0
                    dz = np.abs(z - cz) - sz / 2.0
                    return np.maximum.reduce([dx, dy, dz])

                def capped(x, y, z):
                    return np.maximum(field_fn(x, y, z), box_eval(x, y, z))

                field = capped
        nx, ny, nz = resolution
        if nx < 2 or ny < 2 or nz < 2:
            raise ValueError("resolution 每个维度必须 >= 2")

        xs = np.linspace(xmin, xmax, nx)
        ys = np.linspace(ymin, ymax, ny)
        zs = np.linspace(zmin, zmax, nz)
        grid_x, grid_y, grid_z = np.meshgrid(xs, ys, zs, indexing="ij")
        values = _evaluate_field_values(field, grid_x, grid_y, grid_z)
        triangles = _marching_tetrahedra(xs, ys, zs, values, iso)
        if not triangles:
            raise ValueError("未找到等势面，请调整 bounds 或 iso")

        faces = []
        edge_count: dict[
            Tuple[Tuple[float, float, float], Tuple[float, float, float]], int
        ] = {}
        for tri in triangles:
            if len({tri[0], tri[1], tri[2]}) < 3:
                continue
            try:
                faces.append(make_triangle_face(tri))
            except Exception:
                continue
            pts = [tuple(np.round(p, 8)) for p in tri]
            edges = [(pts[0], pts[1]), (pts[1], pts[2]), (pts[2], pts[0])]
            for a, b in edges:
                key = (a, b) if a <= b else (b, a)
                edge_count[key] = edge_count.get(key, 0) + 1
        sewing = BRepBuilderAPI_Sewing(1e-6)
        for face in faces:
            sewing.Add(face)
        sewing.Perform()
        sewed = sewing.SewedShape()
        shells = []
        if sewed.ShapeType() == TopAbs_SHELL:
            shells.append(sewed)
        else:
            explorer = TopExp_Explorer(sewed, TopAbs_SHELL)
            while explorer.More():
                shells.append(explorer.Current())
                explorer.Next()

        if not shells:
            raise ValueError("未能从等势面构建闭合壳体")

        shell = max(shells, key=shell_metric)

        solid = Solid(solid_from_shell(shell))

        shell_closed_value = shell_is_closed(shell)

        mesh_closed = all(count == 2 for count in edge_count.values())
        report = {
            "bounds": {"min": (xmin, ymin, zmin), "max": (xmax, ymax, zmax)},
            "resolution": resolution,
            "iso": iso,
            "field_min": float(np.min(values)),
            "field_max": float(np.max(values)),
            "triangles": len(triangles),
            "shells": len(shells),
            "mesh_closed": mesh_closed,
            "shell_closed": shell_closed_value,
            "cap_bounds": bool(cap_bounds),
        }
        solid.set_metadata("field_report", report)

        params: Dict[str, object] = {
            "bounds": {
                "min": (xmin, ymin, zmin),
                "max": (xmax, ymax, zmax),
            },
            "resolution": resolution,
            "iso": iso,
            "cap_bounds": bool(cap_bounds),
        }
        if isinstance(original_field, ScalarField):
            params["field_serialization_mode"] = "scalar_field"
            params["field_tree"] = serialize_scalar_field(original_field)
        else:
            params["field_serialization_mode"] = "opaque_callable"
            params["field_callable_repr"] = repr(original_field)

        return _finalize_primitive_solid(
            solid,
            op=_OP_MAKE_FIELD_SURFACE_RSOLID,
            params=params,
            tags={"primitive", "solid", "field"},
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_field_surface_rsolid",
            what_happened="Failed to build an isosurface solid from the scalar field.",
            possible_causes=[
                "The field evaluation returned invalid values or a mismatched shape.",
                "The resolution is too low or the iso value does not intersect the field range.",
                "The marching and sewing steps could not produce a closed shell.",
            ],
            how_to_fix=[
                "Check that the field callable or ScalarField returns finite numeric values.",
                "Use bounds that actually contain the target isosurface.",
                "Increase resolution or adjust the iso value if no surface is found.",
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

        if get_active_session() is not None:
            profile = make_rectangle_rface(
                width,
                height,
                center=bottom_face_center,
                normal=(0.0, 0.0, 1.0),
            )
            solid = extrude_rsolid(profile, (0.0, 0.0, 1.0), depth)
            solid.auto_tag_faces("box")
            solid.apply_tag("geom.primitive.box", propagate=False)
            solid.add_tag("box")
            solid.add_tag(f"bottom center: {bottom_face_center}")
            solid.add_tag(f"size: {width_value}x{height_value}x{depth_value}")
            solid.set_metadata(
                "geo",
                {
                    "type": "box",
                    "size": {"x": width_value, "y": height_value, "z": depth_value},
                    "bottom_face_center": bottom_face_center,
                },
            )
            return solid

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
        solid.apply_tag("geom.primitive.box", propagate=False)
        solid.add_tag("box")
        solid.add_tag(f"bottom center: {bottom_face_center}")
        solid.add_tag(f"size: {width_value}x{height_value}x{depth_value}")
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
            op="make_box",
            params={
                "w": width,
                "h": height,
                "d": depth,
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

        if get_active_session() is not None:
            profile = make_circle_rface(
                bottom_face_center,
                radius,
                normal=axis,
            )
            solid = extrude_rsolid(profile, axis, height)
            solid.auto_tag_faces("cylinder")
            solid.apply_tag("geom.primitive.cylinder", propagate=False)
            solid.add_tag("cylinder")
            solid.add_tag(f"bottom center: {bottom_face_center}")
            solid.add_tag(f"size: {radius_value}x{height_value}")
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
            return solid

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
        solid.apply_tag("geom.primitive.cylinder", propagate=False)
        solid.add_tag("cylinder")
        solid.add_tag(f"bottom center: {bottom_face_center}")
        solid.add_tag(f"size: {radius_value}x{height_value}")
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
            op="make_cylinder",
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

        if get_active_session() is not None:
            axis_value = cast(Tuple[float, float, float], evaluate_value(axis))
            center_value = cast(
                Tuple[float, float, float], evaluate_value(bottom_face_center)
            )
            radial = _pick_perpendicular_unit(axis_value)
            axis_unit = np.array(axis_value, dtype=float)
            axis_unit = axis_unit / float(np.linalg.norm(axis_unit))
            top_center = (
                center_value[0] + float(axis_unit[0]) * height,
                center_value[1] + float(axis_unit[1]) * height,
                center_value[2] + float(axis_unit[2]) * height,
            )
            profile = _make_closed_profile_rface(
                [
                    center_value,
                    (
                        center_value[0] + bottom_radius * float(radial[0]),
                        center_value[1] + bottom_radius * float(radial[1]),
                        center_value[2] + bottom_radius * float(radial[2]),
                    ),
                    (
                        top_center[0] + top_radius * float(radial[0]),
                        top_center[1] + top_radius * float(radial[1]),
                        top_center[2] + top_radius * float(radial[2]),
                    ),
                    top_center,
                ],
                normal=axis_value,
            )
            solid = revolve_rsolid(
                profile,
                axis=axis,
                angle=360.0,
                origin=bottom_face_center,
            )
            solid.apply_tag("geom.primitive.cone", propagate=False)
            solid.add_tag("cone")
            solid.add_tag(f"bottom center: {bottom_face_center}")
            solid.add_tag(
                f"size: bottom_radius: {bottom_radius_value}, top_radius: {top_radius_value}, height: {height_value}"
            )
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
            return solid

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
        solid.apply_tag("geom.primitive.cone", propagate=False)
        solid.add_tag("cone")
        solid.add_tag(f"bottom center: {bottom_face_center}")
        solid.add_tag(
            f"size: bottom_radius: {bottom_radius_value}, top_radius: {top_radius_value}, height: {height_value}"
        )
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
            op="make_cone",
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

        if get_active_session() is not None:
            center_value = cast(Tuple[float, float, float], evaluate_value(center))
            profile = _make_closed_profile_rface(
                [
                    (center_value[0], center_value[1], center_value[2] - radius),
                    (center_value[0] + radius, center_value[1], center_value[2]),
                    (center_value[0], center_value[1], center_value[2] + radius),
                ],
                normal=(0.0, 0.0, 1.0),
            )
            solid = revolve_rsolid(
                profile,
                axis=(0.0, 0.0, 1.0),
                angle=360.0,
                origin=center,
            )
            solid.auto_tag_faces("sphere")
            solid.apply_tag("geom.primitive.sphere", propagate=False)
            solid.add_tag("sphere")
            solid.add_tag(f"center: {center}")
            solid.add_tag(f"radius: {radius_value}")
            solid.set_metadata(
                "geo",
                {
                    "type": "sphere",
                    "radius": radius_value,
                    "center": center,
                },
            )
            return solid

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
        solid.apply_tag("geom.primitive.sphere", propagate=False)
        solid.add_tag("sphere")
        solid.add_tag(f"center: {center}")
        solid.add_tag(f"radius: {radius_value}")
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
            op="make_sphere",
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


def make_spline_redge(
    points: List[Tuple[float, float, float]],
    tangents: Optional[List[Tuple[float, float, float]]] = None,
) -> Edge:
    """Create a spline edge through control points."""
    try:
        if len(points) < 2:
            raise ValueError("至少需要2个控制点")

        cs = get_current_cs()

        # 转换控制点到全局坐标系
        global_points = []
        for point in points:
            point_value = cast(Tuple[float, float, float], evaluate_value(point))
            global_point = cs.transform_point(np.array(point_value))
            global_points.append(tuple(float(v) for v in global_point))

        # 转换切线向量（如果提供）
        global_tangents = None
        if tangents:
            if len(tangents) != len(points):
                raise ValueError("切线向量数量必须与控制点数量一致")
            global_tangents = []
            for tangent in tangents:
                tangent_value = cast(
                    Tuple[float, float, float], evaluate_value(tangent)
                )
                global_tangent = cs.transform_point(np.array(tangent_value)) - cs.origin
                global_tangents.append(tuple(float(v) for v in global_tangent))

        point_tuples = [(float(point[0]), float(point[1]), float(point[2])) for point in global_points]
        tangent_tuples = (
            [(float(t[0]), float(t[1]), float(t[2])) for t in global_tangents] if global_tangents else None
        )
        edge_shape = make_bspline_edge(point_tuples, tangent_tuples)

        return cast(
            Edge,
            _finalize_primitive_shape(
                Edge(edge_shape),
                op=_OP_MAKE_SPLINE_REDGE,
                params={"points": points, "tangents": tangents},
                tags={"primitive", "edge"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_spline_redge",
            what_happened="Failed to create a spline edge.",
            possible_causes=[
                "Fewer than two control points were provided.",
                "One or more control points or tangents are invalid.",
                "The tangent list length does not match the point count.",
            ],
            how_to_fix=[
                "Pass at least two finite 3D control points.",
                "If tangents are provided, make sure there is exactly one tangent per point.",
                "Log the evaluated control points and tangents before retrying.",
            ],
            error=e,
        )


def make_spline_rwire(
    points: List[Tuple[float, float, float]],
    tangents: Optional[List[Tuple[float, float, float]]] = None,
    closed: bool = False,
) -> Wire:
    """Create a spline wire through control points."""
    try:
        if get_active_session() is not None and not closed:
            edge = make_spline_redge(points, tangents)
            return make_wire_from_edges_rwire([edge])

        with suspend_graph_recording():
            edge = make_spline_redge(points, tangents)
        cs = get_current_cs()
        wire_points = []
        for point in points:
            point_value = cast(Tuple[float, float, float], evaluate_value(point))
            global_point = cs.transform_point(np.array(point_value))
            wire_points.append(tuple(float(v) for v in global_point))
        wire_shape = (
            make_polyline_wire(wire_points, closed=closed)
            if closed
            else make_wire_from_edges_ocp([edge.wrapped])
        )
        rv = Wire(wire_shape)
        return cast(
            Wire,
            _finalize_primitive_shape(
                rv,
                op="make_spline_wire",
                params={"points": points, "tangents": tangents, "closed": closed},
                tags={"primitive", "wire"},
            ),
        )
    except Exception as e:
        _wrap_public_api_error(
            operation="make_spline_rwire",
            what_happened="Failed to create a spline wire.",
            possible_causes=[
                "The spline edge could not be created.",
                "The closed-wire fallback received invalid points.",
                "The kernel rejected the resulting wire geometry.",
            ],
            how_to_fix=[
                "Validate the spline control points first.",
                "If closed=True, ensure the point sequence forms a valid loop.",
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
            [(float(point[0]), float(point[1]), float(point[2])) for point in global_points], closed=closed
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
            translated._tags = shape._tags.copy()
            translated._metadata = shape._metadata.copy()
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

        # 复制标签和元数据
        new_shape._tags = shape._tags.copy()
        new_shape._metadata = shape._metadata.copy()
        _copy_runtime_state(shape, new_shape)
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
                rotated._tags = shape._tags.copy()
                rotated._metadata = shape._metadata.copy()
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

            # 复制标签和元数据
            new_shape._tags = shape._tags.copy()
            new_shape._metadata = shape._metadata.copy()
            _copy_runtime_state(shape, new_shape)
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
) -> Solid:
    """Create a solid by extruding a profile."""
    try:
        distance_value = evaluate_scalar(distance)
        if distance_value <= 0:
            raise ValueError("拉伸距离必须大于0")

        cs = get_current_cs()
        direction_value = cast(Tuple[float, float, float], evaluate_value(direction))
        global_direction = cs.transform_point(np.array(direction_value)) - cs.origin

        direction_norm = float(np.linalg.norm(global_direction))
        if direction_norm <= 1e-15:
            raise ValueError("拉伸方向不能是零向量")
        direction_vec = tuple((global_direction / direction_norm * distance_value).tolist())

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

        side_face_count = 0
        profile_face_normal = None
        for face_after_extrusion in solid.get_faces():
            if face_after_extrusion.get_center() == face.get_center():
                face_after_extrusion._tags = profile._tags.copy()
                face_after_extrusion.add_tag("extrusion start face")
                face_after_extrusion._metadata = profile._metadata.copy()
                profile_face_normal = face_after_extrusion.get_normal_at()

        if profile_face_normal is None:
            raise ValueError("没有找到和Profile一致的面对象")

        for face_after_extrusion in solid.get_faces():
            # 开始根据法向量判断顶面底面和侧面
            face_center = face_after_extrusion.get_center()
            # 如果法向量和dir正交，认为是侧面
            face_normal = face_after_extrusion.get_normal_at()
            if face_normal.dot(direction_vec) == 0:
                face_after_extrusion._tags = profile._tags.copy()
                face_after_extrusion.add_tag("extrusion side face")
                side_face_count += 1
                face_after_extrusion.add_tag(f"{side_face_count}")

            # 法向量夹角180度，是顶面
            if face_normal.getAngle(profile_face_normal) == math.pi:
                face_after_extrusion._tags = profile._tags.copy()
                face_after_extrusion.add_tag("extrusion end face")

        # 复制标签和元数据
        solid._tags = profile._tags.copy()
        solid.add_tag("extrusion solid")
        solid._metadata = profile._metadata.copy()

        return _finalize_tracked_solid(
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
) -> Solid:
    """Create a solid by revolving a profile around an axis."""
    try:
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

        # 复制标签和元数据
        solid._tags = profile._tags.copy()
        solid._metadata = profile._metadata.copy()

        return _finalize_tracked_solid(
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


def set_tag(shape: AnyShape, tag: str) -> AnyShape:
    """Attach a tag to a shape."""
    try:
        shape.add_tag(tag)
        return shape
    except Exception as e:
        _wrap_public_api_error(
            operation="set_tag",
            what_happened="Failed to attach the tag to the shape.",
            possible_causes=[
                "The shape is invalid.",
                "The tag value is empty or malformed.",
            ],
            how_to_fix=[
                "Pass a valid shape object.",
                "Use a non-empty tag string.",
            ],
            error=e,
        )


def select_faces_by_tag(solid: Solid, tag: str) -> List[Face]:
    """Select faces by tag."""
    try:
        faces = solid.get_faces()
        return [face for face in faces if face.has_tag(tag)]
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


def select_edges_by_tag(shape: Union[Face, Solid], tag: str) -> List[Edge]:
    """Select edges by tag."""
    try:
        if isinstance(shape, Face):
            edges = [Edge(edge) for edge in shape.wrapped.Edges()]
        elif isinstance(shape, Solid):
            edges = shape.get_edges()
        else:
            raise ValueError("只能从面或实体中选择边")

        return [edge for edge in edges if edge.has_tag(tag)]
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


def union_rsolidlist(
    *solids: Union[Solid, Sequence[Solid]],
    clean: bool = True,
    glue: bool = _DEFAULT_UNION_GLUE,
    tol: Optional[float] = None,
) -> Solid:
    """Compute the boolean union of one or more solids.

    Args:
        solids: One or more Solid objects or sequences of Solid. Nested sequences are
            flattened before processing.
        clean: Call CadQuery's `clean()` after the union to unify same-domain faces
            and remove splitter edges when possible.
        glue: Enable OCC glue mode for touching or partially overlapping inputs.
            Defaults to True for SimpleCAD's standard union behavior.
        tol: Optional fuzzy-boolean tolerance used by the OCC union kernel. When
            omitted, SimpleCAD chooses a conservative scale-aware tolerance.

    Returns:
        Solid: The merged union result.

    Usage:
        All boolean operations (union/cut/intersect) accept a mix of Solid and
        nested sequences of Solid, but now return a single `Solid`.
        If the kernel cannot produce exactly one solid result, the API raises a
        clear error instead of returning a list.

    Examples:
        body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
        rib = make_box_rsolid(2, 4, 4, bottom_face_center=(4, 0, 0))
        merged = union_rsolidlist(body, rib)
        print(merged.get_volume())
    """

    try:
        remaining = _flatten_boolean_solids(solids, "union_rsolidlist")

        if not remaining:
            raise ValueError("union_rsolidlist 至少需要一个Solid输入")

        for solid in remaining:
            if solid.wrapped.IsNull():
                raise ValueError("输入实体无效，无法进行并集运算。")

        if len(remaining) == 1 and not clean:
            return remaining[0]

        effective_tol = _resolve_union_tol(remaining, tol)
        fused_shape = fuse_shapes(
            [solid.wrapped for solid in remaining], glue=glue, tol=effective_tol, clean=clean
        )
        result_shapes = solids_of(fused_shape)

        if len(result_shapes) != 1:
            _warn_if_union_results_remain_separated(
                [Solid(result_shape) for result_shape in result_shapes], effective_tol
            )
        fused_solid = _require_single_boolean_solid(
            result_shapes,
            operation="union_rsolidlist",
            failure_reason="并集结果中未找到有效实体。",
        )

        all_tags = set()
        all_metadata = {}
        for solid in remaining:
            all_tags.update(solid._tags)
            all_metadata.update(solid._metadata)

        fused_solid._tags = all_tags.copy()
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
                op=_OP_MAKE_UNION_RSOLIDLIST,
                params={
                    "input_count": len(remaining),
                    "clean": clean,
                    "glue": glue,
                    "tol": effective_tol,
                },
                source_solid=remaining[0],
                delta=tracked_union_result.delta,
                delta_entries=cast(
                    Dict[str, Dict[str, object]],
                    tracked_union_result.delta_entries,
                ),
                input_shapes=remaining,
            )
        else:
            _attach_track_summary(fused_solid, op=_OP_MAKE_UNION_RSOLIDLIST)
            record_operation_if_active(
                op=_OP_MAKE_UNION_RSOLIDLIST,
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
            operation="union_rsolidlist",
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


def cut_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> Solid:
    """Compute the boolean difference of solids.

    Args:
        solids: One or more Solid objects or sequences of Solid. Nested sequences are
            flattened before processing; the first solid is the base, the rest are
            subtracted in order.

    Returns:
        Solid: The cut result solid.

    Usage:
        Accepts a base solid followed by one or more tool solids, including nested
        sequences, and returns a single `Solid`.
    """
    try:
        remaining = _flatten_boolean_solids(solids, "cut_rsolidlist")

        if not remaining:
            raise ValueError("cut_rsolidlist 至少需要一个Solid输入")

        if len(remaining) == 1:
            return remaining[0]

        # 从第一个实体开始，依次减去其他实体
        result_solid = remaining[0]
        last_delta: Optional[TopoDelta] = None
        last_delta_entries: Optional[Dict[str, Dict[str, object]]] = None
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
                continue
            intersection_obj = Solid(intersection_solids[0])

            if intersection_obj.get_volume() < 1e-12:
                # 没有有效的交集，跳过此次切割
                continue

            tracked = tracked_cut(result_solid, candidate)
            if tracked.solid is None:
                raise ValueError("差集运算失败: OCC 未返回有效实体")

            new_result = tracked.solid
            new_result._tags = result_solid._tags.copy()
            new_result._metadata = result_solid._metadata.copy()
            result_solid = new_result
            last_delta = tracked.delta
            last_delta_entries = cast(
                Dict[str, Dict[str, object]], tracked.delta_entries
            )
            cut_performed = True

        # 保留第一个实体的标签和元数据
        result_solid._tags = remaining[0]._tags.copy()
        result_solid._metadata = remaining[0]._metadata.copy()
        result_solid.add_tag("cut_result")

        if cut_performed and last_delta is not None:
            result_solid = _finalize_tracked_solid(
                result_solid,
                op=_OP_MAKE_CUT_RSOLIDLIST,
                params={"tool_count": len(remaining) - 1},
                source_solid=remaining[0],
                delta=last_delta,
                delta_entries=last_delta_entries,
                input_shapes=remaining,
            )
        else:
            _attach_track_summary(result_solid, op=_OP_MAKE_CUT_RSOLIDLIST)
            record_operation_if_active(
                op=_OP_MAKE_CUT_RSOLIDLIST,
                params={"tool_count": len(remaining) - 1},
                outputs=result_solid,
                input_shapes=remaining,
                context=_current_context_metadata(),
            )

        return result_solid
    except Exception as e:
        _wrap_public_api_error(
            operation="cut_rsolidlist",
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


def intersect_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> Solid:
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
        remaining = _flatten_boolean_solids(solids, "intersect_rsolidlist")

        if not remaining:
            raise ValueError("intersect_rsolidlist 至少需要一个Solid输入")

        if len(remaining) == 1:
            return remaining[0]

        # 从第一个实体开始，依次与后续实体进行交集运算
        result_solid = remaining[0]
        last_delta: Optional[TopoDelta] = None
        last_delta_entries: Optional[Dict[str, Dict[str, object]]] = None
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
            last_delta = tracked.delta
            last_delta_entries = cast(
                Dict[str, Dict[str, object]], tracked.delta_entries
            )
            intersect_performed = True

            # 检查交集是否为空
            if result_solid.get_volume() < 1e-12:
                raise ValueError("交集结果为空或体积过小")

        # 合并所有输入实体的标签和元数据
        all_tags: set = set()
        all_metadata: dict = {}
        for solid in remaining:
            all_tags = (
                all_tags.intersection(solid._tags) if all_tags else solid._tags.copy()
            )
            all_metadata.update(solid._metadata)

        result_solid._tags = all_tags
        result_solid._metadata = all_metadata
        result_solid.add_tag("intersect_result")

        if intersect_performed and last_delta is not None:
            result_solid = _finalize_tracked_solid(
                result_solid,
                op=_OP_MAKE_INTERSECT_RSOLIDLIST,
                params={"input_count": len(remaining)},
                source_solid=remaining[0],
                delta=last_delta,
                delta_entries=last_delta_entries,
                input_shapes=remaining,
            )
        else:
            _attach_track_summary(result_solid, op=_OP_MAKE_INTERSECT_RSOLIDLIST)
            record_operation_if_active(
                op=_OP_MAKE_INTERSECT_RSOLIDLIST,
                params={"input_count": len(remaining)},
                outputs=result_solid,
                input_shapes=remaining,
                context=_current_context_metadata(),
            )

        return result_solid
    except Exception as e:
        _wrap_public_api_error(
            operation="intersect_rsolidlist",
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
# 导出函数
# =============================================================================


_EXPORTABLE_TYPES = (Solid, Face, Wire, Edge, Vertex)


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
        "export 函数只支持 Solid、Face、Wire、Edge、Vertex 或其序列类型的输入"
    )


def export_step(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None:
    """Export shapes to STEP.

    Args:
        shapes: A single exportable shape or any nested sequence of exportable
            shapes. Lists of Solid are supported directly, including list results
            returned by boolean operations.
        filename: Output STEP file path.

    Returns:
        None: Writes the provided shapes into one STEP file.

    Usage:
        Use this function when you want to export one shape or many shapes into the
        same STEP file. Passing `List[Solid]` is valid and often preferred when a
        previous boolean operation returned multiple solids.

    Examples:
        main_body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
        left_cap = make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0))
        right_cap = make_sphere_rsolid(2.0, center=(12.0, 2.0, 2.0))
        body_parts = union_rsolidlist(main_body, [left_cap, right_cap])

        # Export the full list directly; no need to collapse to body_parts[0].
        export_step(body_parts, "rounded_bar.step")
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
                "Pass Solid, Face, Wire, Edge, Vertex, or sequences of those types.",
                "Use a writable file path ending in .step or .stp.",
                "If export still fails, inspect each input shape individually.",
            ],
            error=e,
        )


def export_stl(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None:
    """Export shapes to STL.

    Args:
        shapes: A single Solid or Face, or any nested sequence of Solid/Face.
            Lists of Solid are supported directly, including list results returned
            by boolean operations.
        filename: Output STL file path.

    Returns:
        None: Writes the provided shapes into one STL file.

    Usage:
        Use this function when you want to export one solid or many solids/faces into
        the same STL file. Passing `List[Solid]` is valid and often preferred when a
        previous boolean operation returned multiple solids.

    Examples:
        main_body = make_box_rsolid(10, 4, 4, bottom_face_center=(0, 0, 0))
        left_cap = make_sphere_rsolid(2.0, center=(-2.0, 2.0, 2.0))
        right_cap = make_sphere_rsolid(2.0, center=(12.0, 2.0, 2.0))
        body_parts = union_rsolidlist(main_body, [left_cap, right_cap])

        # Export the list result directly.
        export_stl(body_parts, "rounded_bar.stl")
    """
    try:
        shape_list = _normalize_shape_input(shapes)

        for shape in shape_list:
            if not isinstance(shape, (Solid, Face)):
                raise ValueError("export_stl函数只支持Solid和Face类型的几何体")
        export_stl_shape(make_compound([shape.wrapped for shape in shape_list]), filename)
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
                merged = union_rsolidlist(shaft, cone)
                return merged

            axis_x = _axis_solid((1.0, 0.0, 0.0), axis_len_x)
            axis_y = _axis_solid((0.0, 1.0, 0.0), axis_len_y)
            axis_z = _axis_solid((0.0, 0.0, 1.0), axis_len_z)

            axis_x.apply_tag("axis.x")
            axis_y.apply_tag("axis.y")
            axis_z.apply_tag("axis.z")
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
                (tag for tag in highlight_list if solid.has_tag(tag)), None
            )
            axis_tag = next((tag for tag in axis_colors if solid.has_tag(tag)), None)
            if highlight_tag and highlight_tag not in label_points:
                label_points[highlight_tag] = (
                    0.5 * (bb.xmin + bb.xmax),
                    0.5 * (bb.ymin + bb.ymax),
                    0.5 * (bb.zmin + bb.zmax),
                )

            for face in solid.get_faces():
                face_tag = next(
                    (tag for tag in highlight_list if face.has_tag(tag)), None
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
                    boxstyle="round,pad=0.2", fc="#111111", ec="#ffaa33", alpha=0.9
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
    solid: Solid, edges: Union[Sequence[Edge], ShapeSelector], radius: ScalarLike
) -> Solid:
    """Apply fillets to selected solid edges."""
    try:
        radius_value = evaluate_scalar(radius)
        if radius_value <= 0:
            raise ValueError("圆角半径必须大于0")

        selected_edges = cast(List[Edge], _resolve_selector_or_shapes(solid, edges))
        if not selected_edges:
            raise ValueError("圆角操作至少需要一条边")

        tracked = tracked_fillet(solid, selected_edges, radius_value)
        result = cast(Solid, tracked.shape)

        # 复制标签和元数据
        result._tags = solid._tags.copy()
        result._metadata = solid._metadata.copy()

        return _finalize_tracked_solid(
            result,
            op=_OP_MAKE_FILLET_RSOLID,
            params={
                "radius": radius,
                "edge_count": len(selected_edges),
                "selected_edges": _serialize_shape_refs(selected_edges),
                "selected_edge_indices": _serialize_selection_indices(
                    selected_edges, solid.get_edges()
                ),
                **(
                    {"selection_query": _serialize_selection_query(edges)}
                    if _serialize_selection_query(edges) is not None
                    else {}
                ),
            },
            source_solid=solid,
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[solid],
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
    solid: Solid, edges: Union[Sequence[Edge], ShapeSelector], distance: ScalarLike
) -> Solid:
    """Apply chamfers to selected solid edges."""
    try:
        distance_value = evaluate_scalar(distance)
        if distance_value <= 0:
            raise ValueError("倒角距离必须大于0")

        selected_edges = cast(List[Edge], _resolve_selector_or_shapes(solid, edges))
        if not selected_edges:
            raise ValueError("倒角操作至少需要一条边")

        tracked = tracked_chamfer(solid, selected_edges, distance_value)
        result = cast(Solid, tracked.shape)

        # 复制标签和元数据
        result._tags = solid._tags.copy()
        result._metadata = solid._metadata.copy()

        return _finalize_tracked_solid(
            result,
            op=_OP_MAKE_CHAMFER_RSOLID,
            params={
                "distance": distance,
                "edge_count": len(selected_edges),
                "selected_edges": _serialize_shape_refs(selected_edges),
                "selected_edge_indices": _serialize_selection_indices(
                    selected_edges, solid.get_edges()
                ),
                **(
                    {"selection_query": _serialize_selection_query(edges)}
                    if _serialize_selection_query(edges) is not None
                    else {}
                ),
            },
            source_solid=solid,
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[solid],
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
) -> Solid:
    """Shell a solid to create a hollow part."""
    try:
        thickness_value = evaluate_scalar(thickness)
        if thickness_value <= 0:
            raise ValueError("壁厚必须大于0")

        selected_faces = cast(
            List[Face], _resolve_selector_or_shapes(solid, faces_to_remove)
        )
        if not selected_faces:
            raise ValueError("抽壳操作至少需要一个待移除面")

        # 转换为CADQuery面对象
        tracked = tracked_shell(solid, selected_faces, thickness_value)
        result = cast(Solid, tracked.shape)

        # 复制标签和元数据
        result._tags = solid._tags.copy()
        result._metadata = solid._metadata.copy()

        return _finalize_tracked_solid(
            result,
            op=_OP_MAKE_SHELL_RSOLID,
            params={
                "thickness": thickness,
                "removed_face_count": len(selected_faces),
                "selected_faces": _serialize_shape_refs(selected_faces),
                "selected_face_indices": _serialize_selection_indices(
                    selected_faces, solid.get_faces()
                ),
                **(
                    {"selection_query": _serialize_selection_query(faces_to_remove)}
                    if _serialize_selection_query(faces_to_remove) is not None
                    else {}
                ),
            },
            source_solid=solid,
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[solid],
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


def loft_rsolid(profiles: List[Wire], ruled: bool = False) -> Solid:
    """Create a solid by lofting multiple profiles."""
    try:
        if len(profiles) < 2:
            raise ValueError("放样至少需要2个轮廓")

        tracked = tracked_loft(profiles, ruled=ruled)
        result = cast(Solid, tracked.shape)

        # 合并所有轮廓的标签和元数据
        all_tags = set()
        all_metadata = {}
        for profile in profiles:
            all_tags.update(profile._tags)
            all_metadata.update(profile._metadata)

        result._tags = all_tags
        result._metadata = all_metadata

        return _finalize_tracked_solid(
            result,
            op=_OP_MAKE_LOFT_RSOLID,
            params={"profile_count": len(profiles), "ruled": ruled},
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=profiles,
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


def sweep_rsolid(profile: Face, path: Wire, is_frenet: bool = False) -> Solid:
    """Create a solid by sweeping a profile along a path."""
    make_solid = True  # 默认创建实体
    try:
        tracked = tracked_sweep(profile, path, is_frenet=is_frenet)
        result = cast(Solid, tracked.shape)

        # 合并轮廓和路径的标签和元数据
        result._tags = profile._tags.union(path._tags)
        result._metadata = {**profile._metadata, **path._metadata}

        return _finalize_tracked_solid(
            result,
            op=_OP_MAKE_SWEEP_RSOLID,
            params={"is_frenet": bool(is_frenet)},
            delta=tracked.delta,
            delta_entries=cast(Dict[str, Dict[str, object]], tracked.delta_entries),
            input_shapes=[profile, path],
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
                translated_shape.add_tag(f"linear_pattern_{i + 1}")
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
            s.add_tag(f"linear_pattern_{i + 1}")
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
                rotated_shape.add_tag(f"radial_pattern_{i + 1}")
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
            s.add_tag(f"radial_pattern_{i + 1}")
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
            new_shape._tags = shape._tags.copy()
            new_shape._metadata = shape._metadata.copy()
            new_shape.add_tag("mirrored")
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

        # 复制标签和元数据
        new_shape._tags = shape._tags.copy()
        new_shape._metadata = shape._metadata.copy()
        new_shape.add_tag("mirrored")

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

        # 复制轮廓的标签和元数据
        result._tags = profile._tags.copy()
        result._metadata = profile._metadata.copy()
        result.add_tag("helical_sweep")

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
