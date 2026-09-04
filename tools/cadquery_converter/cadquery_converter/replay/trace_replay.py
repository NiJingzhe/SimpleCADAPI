"""Replay CadQuery traces into SimpleCAD and emit SFTC."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from ..emit_sftc import _emit_cut_tool, _emit_profile_expr, _emit_spline_path, _emit_wire_path_segments
from ..ir import fmt_num, fmt_vec, plane_vectors, point_on_plane, regular_polygon_points
from ..selectors import (
    cq_edges_from_centers_expr,
    cq_extreme_edge_expr,
    cq_face_edges_expr,
    cq_parallel_edge_expr,
    cq_selector_to_ql_hint,
)
from ..sftc_template import ParameterRegistry, emit_sftc_module, feature_comment, result_tag
from ..tracer.trace_schema import GeoFingerprint, OperationTrace, TraceStep
from .op_map import (
    COMMITTING_KIND,
    CONTEXT_ONLY_OPS,
    PATTERN_SETUP_OPS,
    PROFILE_OPS,
)

PLANE_EXTRUDE: Dict[str, Tuple[float, float, float]] = {
    "XY": (0.0, 0.0, 1.0),
    "XZ": (0.0, 1.0, 0.0),
    "YZ": (1.0, 0.0, 0.0),
}


def _as_xy(value: Any) -> Tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (float(value[0]), float(value[1]))
    raise ValueError(f"expected 2D point, got {value!r}")


def _as_vec3(value: Any) -> Tuple[float, float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    raise ValueError(f"expected 3-vector, got {value!r}")


def _cross(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> Tuple[float, float, float]:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _local_to_global(
    origin: Tuple[float, float, float],
    u_dir: Tuple[float, float, float],
    v_dir: Tuple[float, float, float],
    local: Tuple[float, float, float],
    *,
    normal: Optional[Tuple[float, float, float]] = None,
) -> Tuple[float, float, float]:
    """Map workplane-local coords to world (CadQuery toWorldCoords semantics).

    local=(x, y[, z]) where z is along the plane normal when provided.
    """
    nx, ny, nz = normal if normal is not None else (0.0, 0.0, 0.0)
    lz = float(local[2]) if len(local) >= 3 else 0.0
    return (
        origin[0] + local[0] * u_dir[0] + local[1] * v_dir[0] + lz * nx,
        origin[1] + local[0] * u_dir[1] + local[1] * v_dir[1] + lz * ny,
        origin[2] + local[0] * u_dir[2] + local[1] * v_dir[2] + lz * nz,
    )


def _dot(a: Tuple[float, float, float], b: Tuple[float, float, float]) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _project_to_plane(
    point: Tuple[float, float, float],
    origin: Tuple[float, float, float],
    normal: Tuple[float, float, float],
) -> Tuple[float, float, float]:
    """Drop floating-point drift so world-space wires stay coplanar."""
    nn = (normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2) ** 0.5
    if nn < 1e-18:
        return point
    unit = (normal[0] / nn, normal[1] / nn, normal[2] / nn)
    delta = (point[0] - origin[0], point[1] - origin[1], point[2] - origin[2])
    dist = _dot(delta, unit)
    return (
        point[0] - unit[0] * dist,
        point[1] - unit[1] * dist,
        point[2] - unit[2] * dist,
    )


def _global_to_local(
    origin: Tuple[float, float, float],
    u_dir: Tuple[float, float, float],
    v_dir: Tuple[float, float, float],
    point: Tuple[float, float, float],
) -> Tuple[float, float]:
    delta = (point[0] - origin[0], point[1] - origin[1], point[2] - origin[2])
    return (_dot(delta, u_dir), _dot(delta, v_dir))


def _is_named_workplane(plane_name: Optional[str]) -> bool:
    if not plane_name:
        return False
    text = str(plane_name)
    return text in PLANE_EXTRUDE or text.startswith("Plane(")


def _is_workplane_ref(value: Any) -> bool:
    return isinstance(value, dict) and value.get("__workplane_ref__") is True


def _find_path_chain_range(steps: List[TraceStep], end_index: int) -> Tuple[int, int]:
    start = end_index - 1
    while start >= 0:
        step = steps[start]
        if step.op == "Workplane" and _is_named_workplane(step.plane_name):
            return start, end_index
        start -= 1
    return end_index, end_index


def _find_tool_chain_range(steps: List[TraceStep], end_index: int) -> Tuple[int, int]:
    start = end_index - 1
    while start >= 0:
        step = steps[start]
        if step.op == "Workplane" and _is_named_workplane(step.plane_name):
            candidate = start
            cursor = start - 1
            while cursor >= 0 and steps[cursor].op in {
                "circle",
                "rect",
                "polygon",
                "polyline",
                "slot2D",
                "spline",
                "moveTo",
                "lineTo",
                "threePointArc",
                "close",
                "mirrorX",
                "mirrorY",
                "center",
                "transformed",
            }:
                cursor -= 1
            if (
                cursor >= 0
                and steps[cursor].op == "Workplane"
                and _is_named_workplane(steps[cursor].plane_name)
            ):
                candidate = cursor
            return candidate, end_index
        start -= 1
    return end_index, end_index


def filter_meaningful_steps(steps: List[TraceStep]) -> List[TraceStep]:
    filtered: List[TraceStep] = []
    for step in steps:
        if step.op == "Workplane":
            if _is_named_workplane(step.plane_name):
                filtered.append(step)
            continue
        if step.op in {
            "circle",
            "rect",
            "polygon",
            "polyline",
            "slot2D",
            "spline",
            "moveTo",
            "lineTo",
            "threePointArc",
            "close",
            "mirrorX",
            "mirrorY",
        }:
            filtered.append(step)
            continue
        if step.op in {
            "box",
            "cylinder",
            "sphere",
            "extrude",
            "cutBlind",
            "cutThruAll",
            "revolve",
            "loft",
            "hole",
            "sweep",
            "cut",
            "union",
            "intersect",
            "fillet",
            "chamfer",
            "shell",
            "cskHole",
            "faces",
            "edges",
            "workplane",
            "transformed",
            "center",
            "rarray",
            "polarArray",
            "pushPoints",
        }:
            filtered.append(step)
    return filtered


def _resolve_edges(
    body: str,
    step: TraceStep,
    *,
    uses_ql: bool,
    pending_edge_selector: Optional[str] = None,
    pending_face_selector: Optional[str] = None,
) -> Tuple[str, bool]:
    """Resolve chamfer/fillet edge sets without relying on CQ topology indices."""

    edge_selector = step.selector or pending_edge_selector
    if edge_selector:
        parallel = cq_parallel_edge_expr(edge_selector, body)
        if parallel:
            return parallel, uses_ql
        extreme = cq_extreme_edge_expr(edge_selector, body)
        if extreme:
            return extreme, uses_ql
        hint = cq_selector_to_ql_hint(edge_selector, on="edges")
        if hint:
            return f"ql.select({body}.get_edges()).where({hint})", True

    # faces(">X").chamfer: extreme outer edges are a stable stand-in for CadQuery's
    # face-edge expansion (all face-boundary edges are often too broad for OCC).
    if pending_face_selector:
        extreme = cq_extreme_edge_expr(pending_face_selector, body)
        if extreme:
            return extreme, uses_ql
        face_edges = cq_face_edges_expr(pending_face_selector, body)
        if face_edges:
            return face_edges, True

    selections = step.selections or []
    centers: List[Tuple[float, float, float]] = []
    for item in selections:
        center = getattr(item, "center", None)
        if isinstance(center, (list, tuple)) and len(center) >= 3:
            centers.append((float(center[0]), float(center[1]), float(center[2])))
    matched = cq_edges_from_centers_expr(body, centers, tol=0.5)
    if matched:
        return matched, uses_ql

    return f"{body}.get_edges()", uses_ql


def _resolve_faces(body: str, face_selector: Optional[str]) -> Tuple[str, bool]:
    if face_selector:
        hint = cq_selector_to_ql_hint(face_selector, on="faces")
        if hint:
            return f"ql.select({body}.get_faces()).where({hint}).all()", True
    return f"{body}.get_faces()", False


@dataclass
class ReplayState:
    plane: str = "XY"
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    normal: Tuple[float, float, float] = (0.0, 0.0, 1.0)
    u_dir: Tuple[float, float, float] = (1.0, 0.0, 0.0)
    v_dir: Tuple[float, float, float] = (0.0, 1.0, 0.0)
    pending_profile: Optional[Dict[str, Any]] = None
    loft_profiles: List[Dict[str, Any]] = field(default_factory=list)
    pending_rarray: Optional[Dict[str, Any]] = None
    pending_edge_selector: Optional[str] = None
    pending_face_selector: Optional[str] = None
    on_face_workplane: bool = False
    body: str = "body"
    has_body: bool = False
    last_solid: Optional[str] = None
    pending_union_parts: List[str] = field(default_factory=list)
    feature_no: int = 0
    lines: List[str] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    uses_ql: bool = False


class TraceReplayer:
    def __init__(
        self,
        graph_id: str,
        *,
        emit_features: bool = True,
        parameters: Optional[ParameterRegistry] = None,
        tool_mode: bool = False,
        tool_prefix: str = "tool",
    ) -> None:
        self.graph_id = graph_id
        self.state = ReplayState()
        self.parameters = parameters or ParameterRegistry()
        self._current_feature_slug = "feature"
        self._emit_features = emit_features
        self._tool_mode = tool_mode
        self._tool_prefix = tool_prefix
        self._tool_serial = 0
        self._pending_trace_kinds: List[str] = []
        self._feature_units: List[Dict[str, Any]] = []
        self._context_ops: List[str] = []

    def _note_trace_op(self, op: str) -> None:
        if op in PROFILE_OPS or op in PATTERN_SETUP_OPS:
            self._pending_trace_kinds.append(op)
        elif op in CONTEXT_ONLY_OPS or op == "Workplane":
            self._context_ops.append(op)

    def _close_open_feature(self) -> None:
        if not self._feature_units:
            return
        unit = self._feature_units[-1]
        unit["params"] = self.parameters.params_for_feature(int(unit["index"]))
        start = unit.get("sftc_lines", [len(self.state.lines), len(self.state.lines)])[0]
        unit["sftc_lines"] = [start, len(self.state.lines)]

    def _feature(
        self,
        description: str,
        *,
        slug: str = "",
        kind: str = "",
        trace_op: str = "",
    ) -> None:
        if not self._emit_features:
            return
        self._close_open_feature()
        self.state.feature_no += 1
        self._current_feature_slug = slug or description.replace(" ", "_").lower()
        resolved_kind = kind
        if not resolved_kind and trace_op in COMMITTING_KIND:
            resolved_kind = COMMITTING_KIND[trace_op]
        if not resolved_kind:
            resolved_kind = {
                "box": "Box",
                "cylinder": "Cylinder",
                "sphere": "Sphere",
                "extrude": "Extrude",
                "hole": "Hole",
                "revolve": "Revolve",
                "loft": "Loft",
                "sweep": "Sweep",
                "cut": "Cut",
                "union": "Join",
                "intersect": "Intersect",
                "fillet": "Fillet",
                "chamfer": "Chamfer",
                "blind_cut": "Cut",
                "through_cut": "Cut",
                "through_hole": "Hole",
                "pattern_pocket_cut": "Cut",
            }.get(self._current_feature_slug, self._current_feature_slug.title())
        kinds = list(self._pending_trace_kinds)
        if trace_op:
            kinds.append(trace_op)
        elif self._current_feature_slug in COMMITTING_KIND:
            kinds.append(self._current_feature_slug)
        self._pending_trace_kinds = []
        self.state.lines.append(feature_comment(self.state.feature_no, description))
        start_line = len(self.state.lines)
        unit = {
            "index": self.state.feature_no,
            "kind": resolved_kind,
            "slug": self._current_feature_slug,
            "cq_trace_kinds": kinds,
            "params": [],
            "sftc_lines": [start_line, start_line],
            "emitted": True,
        }
        self._feature_units.append(unit)
        self.parameters.set_active_feature(
            self.state.feature_no,
            kind=resolved_kind,
            trace_ops=kinds,
        )

    def _param(self, stem: str, value: float, *, comment: str = "") -> str:
        return self.parameters.auto(stem, value, comment=comment)

    def _build_manifest(self, steps: List[TraceStep]) -> Dict[str, Any]:
        from ..scoring.feature_semantics import build_feature_manifest, identify_feature_units

        self._close_open_feature()
        identified = identify_feature_units(steps)
        return build_feature_manifest(
            identified=identified,
            emitted=self._feature_units,
            unsupported_notes=self.state.unsupported,
            context_only_trace_ops=self._context_ops,
        )

    def _tag(self) -> str:
        return result_tag(self.state.feature_no, self._current_feature_slug)

    def _sync_body(self) -> None:
        self.state.last_solid = self.state.body

    def _commit_solid_var(self, var: str) -> None:
        if not self._tool_mode and var == "body":
            self.state.body = var
        self.state.last_solid = var

    def _union_into_body(self, var: str) -> None:
        """If a new solid was emitted beside an existing body, fuse it in."""
        if self._tool_mode or not self.state.has_body:
            self._commit_solid_var(var)
            if not self._tool_mode:
                self.state.pending_union_parts = [var]
            return
        if var == self.state.body:
            self._commit_solid_var(var)
            if not self.state.pending_union_parts:
                self.state.pending_union_parts = [var]
            return
        self._queue_union_part(var)

    def _queue_union_part(self, var: str) -> None:
        """Defer pairwise fuse so disconnected CQ compounds can merge later."""
        parts = self.state.pending_union_parts
        if not parts:
            parts = [self.state.body]
        if var not in parts:
            parts.append(var)
        self.state.pending_union_parts = parts
        self.state.last_solid = var

    def _ensure_fused_body(self) -> None:
        """Materialize deferred union parts into one manifold body when needed."""
        # Tool solids must chamfer/fillet the tool var, never the parent `body`.
        if self._tool_mode:
            if self.state.last_solid:
                self.state.body = self.state.last_solid
                self.state.has_body = True
                self.state.pending_union_parts = [self.state.last_solid]
            return
        parts = [part for part in self.state.pending_union_parts if part]
        if len(parts) <= 1:
            if len(parts) == 1:
                self.state.body = parts[0]
                self.state.has_body = True
                self.state.last_solid = parts[0]
            return
        body = self.state.body if self.state.has_body else "body"
        # CadQuery allows tangent/compound contacts. Prefer multi-solid fuse first
        # (needed when only the full set connects); then tol; then radial nudge.
        args = ", ".join(parts)
        helper = f"_{body}_smart_fuse"
        self.state.lines.extend(
            [
                f"    _{body}_union_parts = [{args}]",
                f"    _{body}_union_parts = [p for p in _{body}_union_parts if p.get_volume() > 1e-9]",
                f"    if not _{body}_union_parts:",
                "        raise RuntimeError('no solid parts left to fuse')",
                f"    def {helper}(parts):",
                "        def _center(solid):",
                "            faces = solid.get_faces()",
                "            if not faces:",
                "                return (0.0, 0.0, 0.0)",
                "            xs = ys = zs = 0.0",
                "            for face in faces:",
                "                cx, cy, cz = tuple(face.get_center())",
                "                xs += cx; ys += cy; zs += cz",
                "            n = float(len(faces))",
                "            return (xs / n, ys / n, zs / n)",
                "        vol_seed = parts[0].get_volume()",
                "        for tol in (None, 0.5):",
                "            try:",
                "                cand = (",
                "                    scad.union_rsolid(*parts)",
                "                    if tol is None",
                "                    else scad.union_rsolid(*parts, tol=tol)",
                "                )",
                "                if cand.get_volume() > vol_seed + 1e-3:",
                "                    return cand",
                "            except Exception:",
                "                pass",
                "        result = parts[0]",
                "        for part in parts[1:]:",
                "            fused = None",
                "            vol_before = result.get_volume()",
                "            for tol in (None, 0.5):",
                "                try:",
                "                    cand = (",
                "                        scad.union_rsolid(result, part)",
                "                        if tol is None",
                "                        else scad.union_rsolid(result, part, tol=tol)",
                "                    )",
                "                    if cand.get_volume() > vol_before + 1e-3:",
                "                        fused = cand",
                "                        break",
                "                except Exception:",
                "                    fused = None",
                "            if fused is None:",
                "                rc = _center(result)",
                "                pc = _center(part)",
                "                dx, dy, dz = rc[0] - pc[0], rc[1] - pc[1], rc[2] - pc[2]",
                "                norm = (dx * dx + dy * dy + dz * dz) ** 0.5 or 1.0",
                "                for delta in (0.5, 1.0, 2.0, 5.0, 10.0):",
                "                    nudged = scad.translate_shape(",
                "                        part, (dx / norm * delta, dy / norm * delta, dz / norm * delta)",
                "                    )",
                "                    for tol in (None, 0.5):",
                "                        try:",
                "                            cand = (",
                "                                scad.union_rsolid(result, nudged)",
                "                                if tol is None",
                "                                else scad.union_rsolid(result, nudged, tol=tol)",
                "                            )",
                "                            if cand.get_volume() > vol_before + 1e-3:",
                "                                fused = cand",
                "                                break",
                "                        except Exception:",
                "                            fused = None",
                "                    if fused is not None:",
                "                        break",
                "            if fused is None:",
                "                raise RuntimeError('smart fuse failed for tangent/disjoint solids')",
                "            result = fused",
                "        return result",
                f"    {body} = {helper}(_{body}_union_parts)",
            ]
        )
        self.state.body = body
        self.state.has_body = True
        self.state.last_solid = body
        self.state.pending_union_parts = [body]
        self._sync_body()

    def _op_Workplane(self, step: TraceStep) -> None:
        if step.plane_name in PLANE_EXTRUDE:
            self.state.on_face_workplane = False

    def _plane_frame(self) -> Dict[str, Tuple[float, float, float]]:
        return {
            "normal": self.state.normal,
            "extrude": self._extrude_direction(),
            "u": self.state.u_dir,
            "v": self.state.v_dir,
        }

    def _workplane_block(self, var: str, body_lines: List[str], *, indent: str = "    ") -> None:
        inner = indent + "    "
        self.state.lines.append(
            f"{indent}with scad.SimpleWorkplane("
            f"origin={fmt_vec(self.state.origin)}, "
            f"normal={fmt_vec(self.state.normal)}, "
            f"x_dir={fmt_vec(self.state.u_dir)},):"
        )
        for line in body_lines:
            if line.startswith(indent):
                self.state.lines.append(inner + line[len(indent) :])
            else:
                self.state.lines.append(line)

    def _update_plane_frame(self, step: TraceStep) -> None:
        if step.op == "Workplane":
            if step.plane_name in PLANE_EXTRUDE:
                self.state.plane = step.plane_name
                if step.plane_normal and step.plane_x_dir:
                    normal = _as_vec3(step.plane_normal)
                    u_dir = _as_vec3(step.plane_x_dir)
                    self.state.normal = normal
                    self.state.u_dir = u_dir
                    self.state.v_dir = _cross(normal, u_dir)
                else:
                    frame = plane_vectors(self.state.plane)
                    self.state.normal = frame["normal"]
                    self.state.u_dir = frame["u"]
                    self.state.v_dir = frame["v"]
                if step.plane_origin and len(step.plane_origin) >= 3:
                    self.state.origin = (
                        float(step.plane_origin[0]),
                        float(step.plane_origin[1]),
                        float(step.plane_origin[2]),
                    )
            elif step.plane_name and str(step.plane_name).startswith("Plane("):
                if step.plane_origin and len(step.plane_origin) >= 3:
                    self.state.origin = (
                        float(step.plane_origin[0]),
                        float(step.plane_origin[1]),
                        float(step.plane_origin[2]),
                    )
                if step.plane_normal and step.plane_x_dir:
                    normal = _as_vec3(step.plane_normal)
                    u_dir = _as_vec3(step.plane_x_dir)
                    self.state.normal = normal
                    self.state.u_dir = u_dir
                    self.state.v_dir = _cross(normal, u_dir)
            return

        if step.plane_origin and len(step.plane_origin) >= 3:
            self.state.origin = (
                float(step.plane_origin[0]),
                float(step.plane_origin[1]),
                float(step.plane_origin[2]),
            )
        if step.plane_normal and step.plane_x_dir:
            normal = _as_vec3(step.plane_normal)
            u_dir = _as_vec3(step.plane_x_dir)
            self.state.normal = normal
            self.state.u_dir = u_dir
            self.state.v_dir = _cross(normal, u_dir)

    def _global_point(self, local: Tuple[float, float, float]) -> Tuple[float, float, float]:
        return _local_to_global(
            self.state.origin,
            self.state.u_dir,
            self.state.v_dir,
            local,
            normal=self.state.normal,
        )

    def _mirror_point_about_local_axis(
        self,
        point: Tuple[float, float, float],
        *,
        axis: str,
    ) -> Tuple[float, float, float]:
        """Mirror a world point about the workplane local X or Y axis."""
        u, v = _global_to_local(self.state.origin, self.state.u_dir, self.state.v_dir, point)
        if axis == "Y":
            u = -u
        elif axis == "X":
            v = -v
        else:
            raise ValueError(f"unsupported mirror axis: {axis}")
        return _local_to_global(
            self.state.origin,
            self.state.u_dir,
            self.state.v_dir,
            (u, v, 0.0),
            normal=self.state.normal,
        )

    def _extrude_direction(self) -> Tuple[float, float, float]:
        return self.state.normal

    def _hole_extrude_direction(self, normal: Tuple[float, float, float]) -> Tuple[float, float, float]:
        del normal
        if self.state.on_face_workplane:
            return self._cut_direction()
        return self._extrude_direction()

    def _cut_direction(self) -> Tuple[float, float, float]:
        if self.state.on_face_workplane:
            return tuple(-component for component in self.state.normal)
        return self.state.normal

    def _profile_normal(self) -> Tuple[float, float, float]:
        return self.state.normal

    def _attach_frame(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(profile)
        direction = self._extrude_direction()
        enriched["frame"] = {
            "normal": self._profile_normal(),
            "extrude": direction,
            "u": self.state.u_dir,
            "v": self.state.v_dir,
        }
        if "origin" not in profile:
            enriched["origin"] = self.state.origin
        return enriched

    def replay(self, trace: OperationTrace) -> Tuple[str, Dict[str, Any]]:
        steps = filter_meaningful_steps(trace.steps)
        if not steps:
            from ..scoring.feature_semantics import empty_manifest

            return self._emit_module(), {
                "status": "error",
                "error": "no meaningful trace steps",
                "feature_manifest": empty_manifest(),
            }

        consumed: set[int] = set()
        for index, step in enumerate(steps):
            if step.op == "sweep":
                path_arg = step.args[0] if step.args else None
                if isinstance(path_arg, dict) and path_arg.get("__workplane_path__"):
                    start, end = _find_path_chain_range(steps, index)
                    for consumed_index in range(start, end):
                        consumed.add(consumed_index)
            if step.op in {"cut", "union", "intersect"} and step.args and _is_workplane_ref(step.args[0]):
                start, end = _find_tool_chain_range(steps, index)
                for consumed_index in range(start, end):
                    consumed.add(consumed_index)

        for index, step in enumerate(steps):
            if index in consumed:
                continue
            self._update_plane_frame(step)
            self._note_trace_op(step.op)

            if step.op in {"cut", "union", "intersect"} and step.args and _is_workplane_ref(step.args[0]):
                start, end = _find_tool_chain_range(steps, index)
                try:
                    tool_lines, tool_var, tool_unsupported = self._replay_tool_steps(
                        steps[start:end],
                        prefix=f"tool_{index}",
                    )
                    self.state.lines.extend(tool_lines)
                    self.state.unsupported.extend(tool_unsupported)
                    self._apply_boolean(step.op, tool_var)
                except Exception as exc:
                    self.state.unsupported.append(f"{step.op}: {exc}")
                continue

            if step.op == "sweep":
                path_arg = step.args[0] if step.args else None
                path_steps = None
                if isinstance(path_arg, dict) and path_arg.get("__workplane_path__"):
                    start, end = _find_path_chain_range(steps, index)
                    path_steps = steps[start:end]
                try:
                    self._op_sweep(step, path_steps=path_steps)
                except Exception as exc:
                    self.state.unsupported.append(f"sweep: {exc}")
                continue

            handler = getattr(self, f"_op_{step.op}", None)
            if handler is None:
                self.state.unsupported.append(f"unsupported op: {step.op}")
                continue
            try:
                handler(step)
            except Exception as exc:
                self.state.unsupported.append(f"{step.op}: {exc}")

        manifest = self._build_manifest(steps)
        self._ensure_fused_body()
        if not self.state.has_body:
            return self._emit_module(), {
                "status": "error",
                "error": "no solid produced",
                "unsupported": list(self.state.unsupported),
                "feature_count": self.state.feature_no,
                "feature_manifest": manifest,
            }

        return self._emit_module(), {
            "status": "partial" if self.state.unsupported else "ok",
            "unsupported": list(self.state.unsupported),
            "feature_count": self.state.feature_no,
            "feature_manifest": manifest,
        }

    def _replay_tool_steps(
        self,
        steps: List[TraceStep],
        *,
        prefix: str,
    ) -> Tuple[List[str], str, List[str]]:
        sub = TraceReplayer(
            self.graph_id,
            emit_features=False,
            parameters=self.parameters,
            tool_mode=True,
            tool_prefix=prefix,
        )
        sub_consumed: set[int] = set()
        for index, step in enumerate(steps):
            if step.op == "sweep":
                path_arg = step.args[0] if step.args else None
                if isinstance(path_arg, dict) and path_arg.get("__workplane_path__"):
                    start, end = _find_path_chain_range(steps, index)
                    for consumed_index in range(start, end):
                        sub_consumed.add(consumed_index)
        for sub_index, step in enumerate(steps):
            if sub_index in sub_consumed:
                continue
            sub._update_plane_frame(step)
            if step.op == "sweep":
                path_arg = step.args[0] if step.args else None
                path_steps = None
                if isinstance(path_arg, dict) and path_arg.get("__workplane_path__"):
                    start, end = _find_path_chain_range(steps, sub_index)
                    path_steps = steps[start:end]
                sub._op_sweep(step, path_steps=path_steps)
                continue
            handler = getattr(sub, f"_op_{step.op}", None)
            if handler is None:
                sub.state.unsupported.append(f"unsupported op: {step.op}")
                continue
            try:
                handler(step)
            except Exception as exc:
                sub.state.unsupported.append(f"{step.op}: {exc}")
        tool_var = sub.state.last_solid
        if tool_var is None and sub.state.has_body:
            tool_var = sub.state.body
        if tool_var is None:
            return sub.state.lines, "", list(sub.state.unsupported)
        return sub.state.lines, tool_var, list(sub.state.unsupported)

    def _apply_boolean(self, op: str, tool_var: str) -> None:
        if not tool_var:
            self.state.unsupported.append(f"{op} without distinct tool solid")
            return
        self._feature(f"boolean {op}", slug=op, kind=COMMITTING_KIND.get(op, op.title()), trace_op=op)
        body = self.state.body
        if not self.state.has_body:
            self.state.has_body = True
            self.state.body = "body"
            self.state.lines.append(f"    {body} = {tool_var}")
            self.state.pending_union_parts = [body]
            self._commit_solid_var(body)
            return
        if op == "union":
            self._queue_union_part(tool_var)
            return
        parts = [part for part in self.state.pending_union_parts if part]
        if not parts:
            parts = [body]
        # CadQuery cuts on a multi-body compound can leave disconnected siblings
        # (hub + rim). Fusing first then cutting under SimpleCAD's single-solid
        # contract drops siblings — cut each deferred part in place instead.
        if op == "cut" and len(parts) > 1:
            for part in parts:
                self.state.lines.extend(
                    [
                        "    try:",
                        f"        {part} = scad.cut_rsolid({part}, {tool_var})",
                        "    except Exception:",
                        "        pass",
                    ]
                )
            self.state.pending_union_parts = parts
            self.state.body = parts[0]
            self.state.has_body = True
            self._sync_body()
            return
        self._ensure_fused_body()
        body = self.state.body
        if op == "cut":
            self.state.lines.append(f"    {body} = scad.cut_rsolid({body}, {tool_var})")
        else:
            self.state.lines.append(f"    {body} = scad.intersect_rsolid({body}, {tool_var})")
        self.state.pending_union_parts = [body]
        self._sync_body()

    def _build_path_wire(self, path_steps: List[TraceStep], prefix: str) -> Tuple[List[str], str]:
        sub = TraceReplayer(
            self.graph_id,
            emit_features=False,
            parameters=self.parameters,
            tool_mode=True,
        )
        for step in path_steps:
            sub._update_plane_frame(step)
            handler = getattr(sub, f"_op_{step.op}", None)
            if handler is None:
                continue
            handler(step)
        if sub.state.pending_profile is None:
            raise ValueError("path chain produced no wire profile")
        profile = sub.state.pending_profile
        if profile.get("kind") == "spline_path":
            return _emit_spline_path(profile, prefix)
        profile = sub._finalize_wire_profile()
        return _emit_wire_path_segments(profile, prefix)

    def _op_sweep(self, step: TraceStep, *, path_steps: Optional[List[TraceStep]]) -> None:
        if self.state.pending_profile is None:
            self.state.unsupported.append("sweep without pending profile")
            return
        profile = self._finalize_wire_profile()
        is_frenet = bool(step.kwargs.get("isFrenet", False))
        path_arg = step.args[0] if step.args else None
        var = self._assign_body_var()
        self._feature("sweep", slug="sweep", kind="Sweep", trace_op="sweep")
        profile_lines, profile_expr = _emit_profile_expr(profile, var)
        self.state.lines.extend(profile_lines)

        if isinstance(path_arg, dict) and path_arg.get("__helix__"):
            helix = path_arg["__helix__"]
            center = _as_vec3(helix.get("center", (0.0, 0.0, 0.0)))
            direction = _as_vec3(helix.get("dir", (0.0, 0.0, 1.0)))
            pitch = self._param("helix_pitch", float(helix["pitch"]), comment="helix pitch")
            height = self._param("helix_height", float(helix["height"]), comment="helix height")
            radius = self._param("helix_radius", float(helix["radius"]), comment="helix radius")
            self.state.lines.append(
                f"    {var}_path = scad.make_helix_rwire("
                f"pitch={pitch}, height={height}, radius={radius}, "
                f"center={fmt_vec(center)}, dir={fmt_vec(direction)},)"
            )
            path_expr = f"{var}_path"
        elif path_steps:
            path_lines, path_expr = self._build_path_wire(path_steps, f"{var}_path")
            self.state.lines.extend(path_lines)
        else:
            self.state.unsupported.append("sweep without path")
            return

        tag = self._tag()
        self.state.lines.append(
            f"    {var} = scad.sweep_rsolid("
            f"profile={profile_expr}, path={path_expr}, "
            f"is_frenet={str(is_frenet)}, result_tag={tag!r},)"
        )
        self._union_into_body(var)
        self.state.pending_profile = None

    def _finalize_wire_profile(self) -> Dict[str, Any]:
        profile = self.state.pending_profile
        if profile is None:
            raise ValueError("missing pending profile")
        if profile.get("kind") != "wire_path":
            return self._attach_frame(profile)
        origin = self.state.origin
        normal = self.state.normal
        segments: List[Dict[str, Any]] = []
        for segment in profile["segments"]:
            cleaned = dict(segment)
            cleaned["start"] = _project_to_plane(segment["start"], origin, normal)
            cleaned["end"] = _project_to_plane(segment["end"], origin, normal)
            if "mid" in segment and segment["mid"] is not None:
                cleaned["mid"] = _project_to_plane(segment["mid"], origin, normal)
            segments.append(cleaned)
        points: List[Tuple[float, float, float]] = []
        for segment in segments:
            if segment["kind"] == "line":
                if not points:
                    points.append(segment["start"])
                points.append(segment["end"])
            elif segment["kind"] == "arc3":
                points.extend([segment["start"], segment["mid"], segment["end"]])
        if profile.get("closed") and points and points[0] != points[-1]:
            points.append(points[0])
        return self._attach_frame(
            {
                "kind": "wire_path",
                "plane": self.state.plane,
                "origin": origin,
                "segments": segments,
                "points": points,
                "closed": profile.get("closed", False),
            }
        )

    def _stash_profile_for_loft(self) -> None:
        if self.state.pending_profile is None:
            return
        self.state.loft_profiles.append(self._finalize_wire_profile())
        self.state.pending_profile = None

    def _append_wire_segment(
        self,
        *,
        kind: str,
        start: Tuple[float, float, float],
        end: Tuple[float, float, float],
        mid: Optional[Tuple[float, float, float]] = None,
    ) -> None:
        if self.state.pending_profile is None or self.state.pending_profile.get("kind") != "wire_path":
            self.state.pending_profile = {
                "kind": "wire_path",
                "plane": self.state.plane,
                "origin": self.state.origin,
                "segments": [],
                "closed": False,
                "cursor": start,
            }
        segment: Dict[str, Any] = {"kind": kind, "start": start, "end": end}
        if mid is not None:
            segment["mid"] = mid
        self.state.pending_profile["segments"].append(segment)
        self.state.pending_profile["cursor"] = end

    def _apply_plane_origin(self, step: TraceStep) -> None:
        self._update_plane_frame(step)

    def _op_transformed(self, step: TraceStep) -> None:
        # CQ can loft across profiles separated by transformed(); stash the
        # current profile before the plane jump so loft sees both sections.
        if self.state.pending_profile is not None:
            self._stash_profile_for_loft()
        # Plane origin/normal/u/v are applied via _update_plane_frame from post-transform trace state.
        del step

    def _local_slot_point(
        self,
        u: float,
        v: float,
        angle_deg: float,
    ) -> Tuple[float, float, float]:
        if abs(angle_deg) > 1e-9:
            rad = math.radians(angle_deg)
            cos_a = math.cos(rad)
            sin_a = math.sin(rad)
            u, v = u * cos_a - v * sin_a, u * sin_a + v * cos_a
        return self._global_point((u, v, 0.0))

    def _op_slot2D(self, step: TraceStep) -> None:
        length = self._param("slot_length", float(step.args[0]), comment="slot length")
        width = self._param("slot_width", float(step.args[1]), comment="slot width")
        angle = float(step.args[2]) if len(step.args) > 2 else 0.0
        width_value = float(step.args[1])
        length_value = float(step.args[0])
        radius = width_value / 2.0
        half_straight = max((length_value - width_value) / 2.0, 0.0)
        start = self._local_slot_point(-half_straight, radius, angle)
        top_end = self._local_slot_point(half_straight, radius, angle)
        right_mid = self._local_slot_point(half_straight + radius, 0.0, angle)
        right_end = self._local_slot_point(half_straight, -radius, angle)
        bottom_end = self._local_slot_point(-half_straight, -radius, angle)
        left_mid = self._local_slot_point(-half_straight - radius, 0.0, angle)
        segments: List[Dict[str, Any]] = [
            {"kind": "line", "start": start, "end": top_end},
            {"kind": "arc3", "start": top_end, "mid": right_mid, "end": right_end},
            {"kind": "line", "start": right_end, "end": bottom_end},
            {"kind": "arc3", "start": bottom_end, "mid": left_mid, "end": start},
        ]
        self.state.pending_profile = {
            "kind": "wire_path",
            "plane": self.state.plane,
            "origin": self.state.origin,
            "segments": segments,
            "closed": True,
            "length_param": length,
            "width_param": width,
        }

    def _op_spline(self, step: TraceStep) -> None:
        raw_points = step.args[0] if step.args else []
        global_points: List[Tuple[float, float, float]] = []
        for raw in raw_points:
            if isinstance(raw, (list, tuple)):
                local = _as_vec3(raw[:3])
            else:
                local = _as_vec3(raw)
            global_points.append(self._global_point(local))
        self.state.pending_profile = {
            "kind": "spline_path",
            "plane": self.state.plane,
            "origin": self.state.origin,
            "points": global_points,
        }

    def _op_workplane(self, step: TraceStep) -> None:
        self._stash_profile_for_loft()
        self.state.on_face_workplane = True
        # Face selector was consumed to place this workplane.
        self.state.pending_face_selector = None
        offset = step.kwargs.get("offset")
        if offset is not None:
            normal = plane_vectors(self.state.plane)["normal"]
            delta = float(offset)
            self.state.origin = (
                self.state.origin[0] + normal[0] * delta,
                self.state.origin[1] + normal[1] * delta,
                self.state.origin[2] + normal[2] * delta,
            )
        self._apply_plane_origin(step)

    def _op_center(self, step: TraceStep) -> None:
        if len(step.args) >= 2:
            xy = (float(step.args[0]), float(step.args[1]))
        elif step.args:
            xy = _as_xy(step.args[0])
        else:
            return
        self.state.origin = point_on_plane(self.state.plane, self.state.origin, xy, 0.0)

    def _profile_center(self) -> Tuple[float, float, float]:
        pending = self.state.pending_profile
        if pending and pending.get("kind") == "wire_path":
            cursor = pending.get("cursor")
            if isinstance(cursor, (list, tuple)) and len(cursor) >= 3:
                return (float(cursor[0]), float(cursor[1]), float(cursor[2]))
        return self.state.origin

    def _op_circle(self, step: TraceStep) -> None:
        radius = self._param("outer_radius", float(step.args[0]), comment="profile radius")
        self.state.pending_profile = {
            "kind": "circle",
            "radius": radius,
            "plane": self.state.plane,
            "origin": self._profile_center(),
        }

    def _op_rect(self, step: TraceStep) -> None:
        width = self._param("rect_width", float(step.args[0]), comment="rect width")
        height = self._param("rect_height", float(step.args[1]), comment="rect height")
        self.state.pending_profile = {
            "kind": "rect",
            "width": width,
            "height": height,
            "plane": self.state.plane,
            "origin": self.state.origin,
        }

    def _op_polygon(self, step: TraceStep) -> None:
        n_sides = int(step.args[0])
        diameter = float(step.args[1])
        diameter_expr = self._param(
            "polygon_diameter",
            diameter,
            comment="polygon circumscribed diameter (across-corners)",
        )
        points = regular_polygon_points(n_sides, diameter, self.state.plane, self.state.origin)
        segments: List[Dict[str, Any]] = []
        for index, start in enumerate(points):
            end = points[(index + 1) % len(points)]
            segments.append({"kind": "line", "start": start, "end": end})
        self.state.pending_profile = {
            "kind": "wire_path",
            "plane": self.state.plane,
            "origin": self.state.origin,
            "segments": segments,
            "closed": True,
            # Keep semantic diameter visible/referenced for QA/edit even though
            # the wire is currently emitted from precomputed points.
            "diameter_param": diameter_expr,
        }

    def _op_polyline(self, step: TraceStep) -> None:
        raw_points = step.args[0]
        if self.state.pending_profile:
            kind = self.state.pending_profile.get("kind")
            if kind == "polyline":
                existing = self.state.pending_profile.get("points", [])
                if len(existing) >= len(raw_points):
                    return
            if kind == "wire_path" and self.state.pending_profile.get("closed"):
                segments = self.state.pending_profile.get("segments", [])
                if segments and segments[0]["start"] == segments[-1]["end"]:
                    return
        points = [
            self._global_point(
                (
                    float(item[0]),
                    float(item[1]),
                    float(item[2]) if len(item) >= 3 else 0.0,
                )
            )
            for item in raw_points
        ]
        segments: List[Dict[str, Any]] = []
        for index, start in enumerate(points):
            end = points[(index + 1) % len(points)]
            segments.append({"kind": "line", "start": start, "end": end})
        self.state.pending_profile = {
            "kind": "wire_path",
            "plane": self.state.plane,
            "origin": self.state.origin,
            "segments": segments,
            "closed": True,
        }

    def _op_moveTo(self, step: TraceStep) -> None:
        start = self._global_point((float(step.args[0]), float(step.args[1]), 0.0))
        self.state.pending_profile = {
            "kind": "wire_path",
            "plane": self.state.plane,
            "origin": self.state.origin,
            "segments": [],
            "closed": False,
            "cursor": start,
        }

    def _op_lineTo(self, step: TraceStep) -> None:
        end = self._global_point((float(step.args[0]), float(step.args[1]), 0.0))
        cursor = (
            self.state.pending_profile.get("cursor")
            if self.state.pending_profile
            else self.state.origin
        )
        self._append_wire_segment(kind="line", start=cursor, end=end)

    def _op_threePointArc(self, step: TraceStep) -> None:
        mid = self._global_point(
            (float(step.args[0][0]), float(step.args[0][1]), float(step.args[0][2]) if len(step.args[0]) >= 3 else 0.0)
        )
        end = self._global_point(
            (float(step.args[1][0]), float(step.args[1][1]), float(step.args[1][2]) if len(step.args[1]) >= 3 else 0.0)
        )
        cursor = (
            self.state.pending_profile.get("cursor")
            if self.state.pending_profile
            else self.state.origin
        )
        self._append_wire_segment(kind="arc3", start=cursor, mid=mid, end=end)

    def _op_close(self, step: TraceStep) -> None:
        if self.state.pending_profile and self.state.pending_profile.get("kind") == "wire_path":
            segments = self.state.pending_profile.get("segments", [])
            if segments:
                start = segments[0]["start"]
                end = segments[-1]["end"]
                if start != end:
                    self._append_wire_segment(kind="line", start=end, end=start)
            self.state.pending_profile["closed"] = True

    def _mirror_pending_wire(self, *, axis: str) -> None:
        profile = self.state.pending_profile
        if profile is None or profile.get("kind") != "wire_path":
            self.state.unsupported.append(f"mirror{axis} without pending wire profile")
            return
        segments = list(profile.get("segments") or [])
        if not segments:
            self.state.unsupported.append(f"mirror{axis} with empty wire profile")
            return

        def mirror_pt(point: Tuple[float, float, float]) -> Tuple[float, float, float]:
            return self._mirror_point_about_local_axis(point, axis=axis)

        mirrored: List[Dict[str, Any]] = []
        for segment in reversed(segments):
            mirrored_seg: Dict[str, Any] = {
                "kind": segment["kind"],
                "start": mirror_pt(segment["end"]),
                "end": mirror_pt(segment["start"]),
            }
            if segment.get("mid") is not None:
                mirrored_seg["mid"] = mirror_pt(segment["mid"])
            mirrored.append(mirrored_seg)

        # Connect original end to mirrored start when they differ (off-axis tip).
        join_start = segments[-1]["end"]
        join_end = mirrored[0]["start"]
        combined = list(segments)
        if join_start != join_end:
            combined.append({"kind": "line", "start": join_start, "end": join_end})
        combined.extend(mirrored)
        close_start = combined[-1]["end"]
        close_end = combined[0]["start"]
        if close_start != close_end:
            combined.append({"kind": "line", "start": close_start, "end": close_end})

        profile["segments"] = combined
        profile["closed"] = True
        profile["cursor"] = combined[-1]["end"]

    def _op_mirrorY(self, step: TraceStep) -> None:
        del step
        self._mirror_pending_wire(axis="Y")

    def _op_mirrorX(self, step: TraceStep) -> None:
        del step
        self._mirror_pending_wire(axis="X")

    def _op_rarray(self, step: TraceStep) -> None:
        if len(step.args) < 4:
            return
        self.state.pending_rarray = {
            "x_spacing": float(step.args[0]),
            "y_spacing": float(step.args[1]),
            "x_count": int(step.args[2]),
            "y_count": int(step.args[3]),
        }

    def _op_polarArray(self, step: TraceStep) -> None:
        if not step.args:
            return
        radius = float(step.args[0])
        start_angle = float(step.args[1]) if len(step.args) >= 2 else 0.0
        if len(step.args) >= 4:
            span = float(step.args[2])
            count = int(step.args[3])
        elif len(step.args) >= 3:
            span = 360.0
            count = int(step.args[2])
        else:
            span = 360.0
            count = int(step.args[1]) if len(step.args) >= 2 else 1
            start_angle = 0.0
        count = max(count, 1)
        step_angle = span / count
        points = []
        for index in range(count):
            angle = math.radians(start_angle + index * step_angle)
            points.append((radius * math.cos(angle), radius * math.sin(angle), 0.0))
        self.state.pending_rarray = {
            "polar": True,
            "radius": radius,
            "count": count,
            "start_angle": start_angle,
            "points": points,
        }

    def _op_pushPoints(self, step: TraceStep) -> None:
        if not step.args:
            return
        raw_points = step.args[0]
        points = []
        for point in raw_points:
            if isinstance(point, str):
                continue
            if isinstance(point, (list, tuple)) and len(point) >= 2:
                z = float(point[2]) if len(point) >= 3 else 0.0
                points.append((float(point[0]), float(point[1]), z))
        if not points:
            return
        if self.state.pending_rarray and (
            "x_count" in self.state.pending_rarray or "polar" in self.state.pending_rarray
        ):
            self.state.pending_rarray["points"] = points
        else:
            self.state.pending_rarray = {"points": points}

    def _assign_body_var(self) -> str:
        if not self.state.has_body:
            self.state.has_body = True
            if self._tool_mode:
                self._tool_serial += 1
                var = f"{self._tool_prefix}_{self._tool_serial}"
                self.state.body = var
            else:
                var = "body"
                self.state.body = var
            self.state.last_solid = var
            return var
        if self._tool_mode:
            self._tool_serial += 1
            var = f"{self._tool_prefix}_{self._tool_serial}"
            # Keep chamfer/fillet targeting the latest tool solid.
            self.state.body = var
        else:
            var = f"solid_{self.state.feature_no + 1}"
        self.state.last_solid = var
        return var

    def _emit_solid_from_profile(
        self,
        var: str,
        profile: Dict[str, Any],
        *,
        distance: float | str,
        result_tag: str = "",
    ) -> None:
        profile = self._attach_frame(profile) if "frame" not in profile else profile
        if profile.get("kind") == "circle" and isinstance(distance, str):
            pass  # radius already registered in pending profile
        profile_lines, profile_expr = _emit_profile_expr(profile, var)
        self.state.lines.extend(profile_lines)
        if profile.get("diameter_param"):
            # Keep polygon diameter referenced for QA/edit even with precomputed wires.
            self.state.lines.append(f"    _ = {profile['diameter_param']}  # polygon diameter")
        direction = profile.get("frame", self._plane_frame()).get("extrude", self.state.normal)
        dist_expr = distance if isinstance(distance, str) else fmt_num(distance)
        tag = f", result_tag={result_tag!r}" if result_tag else ""
        self.state.lines.append(
            f"    {var} = scad.extrude_rsolid("
            f"profile={profile_expr}, direction={fmt_vec(direction)}, "
            f"distance={dist_expr}{tag},)"
        )

    def _op_box(self, step: TraceStep) -> None:
        self._feature("box", slug="box", kind="Box", trace_op="box")
        w = self._param("width", float(step.args[0]), comment="box width")
        h = self._param("height", float(step.args[1]), comment="box height")
        d = self._param("depth", float(step.args[2]), comment="box depth")
        var = self._assign_body_var()
        self._workplane_block(
            var,
            [
                f"    {var} = scad.make_box_rsolid("
                f"width={w}, height={h}, depth={d}, "
                f"bottom_face_center=(0, 0, -({d}) / 2.0), "
                f"result_tag={self._tag()!r},)"
            ],
        )
        self._union_into_body(var)
        self.state.pending_profile = None

    def _op_cylinder(self, step: TraceStep) -> None:
        self._feature("cylinder", slug="cylinder", kind="Cylinder", trace_op="cylinder")
        height = float(step.args[0])
        radius = float(step.args[1])
        height_expr = self._param("cylinder_height", height, comment="cylinder height")
        radius_expr = self._param("cylinder_radius", radius, comment="cylinder radius")
        var = self._assign_body_var()
        # Emit in the active SimpleWorkplane local frame: local +Z is the plane normal.
        # Passing a world-space axis here double-applies the frame and flips YZ/XZ parts.
        self._workplane_block(
            var,
            [
                f"    {var} = scad.make_cylinder_rsolid("
                f"radius={radius_expr}, height={height_expr}, "
                f"bottom_face_center=(0, 0, -({height_expr}) / 2.0), "
                f"axis=(0, 0, 1),)"
            ],
        )
        self._union_into_body(var)
        self.state.pending_profile = None

    def _op_sphere(self, step: TraceStep) -> None:
        self._feature("sphere", slug="sphere", kind="Sphere", trace_op="sphere")
        radius = float(step.args[0])
        radius_expr = self._param("sphere_radius", radius, comment="sphere radius")
        var = self._assign_body_var()
        self.state.lines.append(
            f"    {var} = scad.make_sphere_rsolid("
            f"radius={radius_expr}, center={fmt_vec(self.state.origin)},)"
        )
        self._union_into_body(var)
        self.state.pending_profile = None

    def _op_extrude(self, step: TraceStep) -> None:
        if self.state.pending_profile is None:
            self.state.unsupported.append("extrude without pending profile")
            return
        distance = float(step.args[0])
        taper = step.kwargs.get("taper")
        profile = self._finalize_wire_profile()
        if self.state.pending_rarray and not step.kwargs.get("both") and taper is None:
            self._emit_pattern_extrude(profile, distance)
            self.state.pending_profile = None
            self.state.pending_rarray = None
            return
        kind = profile.get("kind", "profile")
        if kind == "circle":
            self._feature("extrude circle", slug="extrude", kind="Extrude", trace_op="extrude")
        elif kind == "rect":
            self._feature("extrude rectangle", slug="extrude", kind="Extrude", trace_op="extrude")
        else:
            self._feature("extrude profile", slug="extrude", kind="Extrude", trace_op="extrude")

        direction = self._extrude_direction()
        dist_value = abs(distance)
        if distance < 0:
            direction = tuple(-component for component in direction)
        dist = self._param("extrude_distance", dist_value, comment="extrude distance")
        var = self._assign_body_var()

        if taper is not None and kind == "circle":
            self._emit_taper_extrude_circle(
                var,
                profile,
                distance=dist,
                direction=direction,
                taper_deg=float(taper),
            )
            self._union_into_body(var)
            self.state.pending_profile = None
            return

        if taper is not None:
            self.state.unsupported.append(f"extrude taper unsupported for profile kind {kind}")

        if step.kwargs.get("both"):
            profile_lines, profile_expr = _emit_profile_expr(profile, var)
            self.state.lines.extend(profile_lines)
            # CadQuery both=True extrudes `distance` in each direction (total 2x).
            offset = (
                f"(-({dist}) * {direction[0]}, "
                f"-({dist}) * {direction[1]}, "
                f"-({dist}) * {direction[2]})"
            )
            self.state.lines.extend(
                [
                    f"    {var}_profile = scad.translate({profile_expr}, {offset})",
                    f"    {var} = scad.extrude_rsolid("
                    f"profile={var}_profile, direction={fmt_vec(direction)}, "
                    f"distance=({dist}) * 2.0, result_tag={self._tag()!r},)",
                ]
            )
        else:
            profile = dict(profile)
            frame = dict(profile.get("frame", self._plane_frame()))
            frame["extrude"] = direction
            profile["frame"] = frame
            self._emit_solid_from_profile(var, profile, distance=dist, result_tag=self._tag())
        self._union_into_body(var)
        self.state.pending_profile = None

    def _emit_taper_extrude_circle(
        self,
        var: str,
        profile: Dict[str, Any],
        *,
        distance: str,
        direction: Tuple[float, float, float],
        taper_deg: float,
    ) -> None:
        """Approximate CadQuery extrude(..., taper=deg) via loft of start/end circles."""
        origin = profile.get("origin", self.state.origin)
        normal = profile.get("frame", self._plane_frame()).get("normal", self.state.normal)
        radius = profile["radius"]
        radius_expr = radius if isinstance(radius, str) else fmt_num(float(radius))
        taper_expr = self._param("extrude_taper", taper_deg, comment="extrude taper angle (deg)")
        # CQ positive taper shrinks along the extrude direction.
        end_radius = f"(({radius_expr}) - ({distance}) * math.tan(math.radians({taper_expr})))"
        end_center = (
            f"({fmt_num(origin[0])} + ({distance}) * {fmt_num(direction[0])}, "
            f"{fmt_num(origin[1])} + ({distance}) * {fmt_num(direction[1])}, "
            f"{fmt_num(origin[2])} + ({distance}) * {fmt_num(direction[2])})"
        )
        self.state.lines.extend(
            [
                f"    {var}_p0 = scad.make_circle_rwire("
                f"center={fmt_vec(origin)}, radius={radius_expr}, normal={fmt_vec(normal)},)",
                f"    {var}_p1 = scad.make_circle_rwire("
                f"center={end_center}, radius={end_radius}, normal={fmt_vec(normal)},)",
                f"    {var} = scad.loft_rsolid(profiles=[{var}_p0, {var}_p1], "
                f"result_tag={self._tag()!r},)",
            ]
        )

    def _emit_pattern_extrude(self, profile: Dict[str, Any], distance: float) -> None:
        pattern = self.state.pending_rarray or {}
        if "x_count" not in pattern and "points" not in pattern:
            self.state.unsupported.append("pattern extrude without rarray or pushPoints")
            return
        if not self.state.has_body:
            self.state.unsupported.append("pattern extrude without base body")
            return

        self._feature("patterned extrude", slug="extrude", kind="Extrude", trace_op="extrude")
        dist = self._param("extrude_distance", distance, comment="extrude distance")
        body = self.state.body
        frame = self._plane_frame()
        direction = self._extrude_direction()
        normal = frame["normal"]
        u_dir = self.state.u_dir
        v_dir = self.state.v_dir
        base_origin = profile.get("origin", self.state.origin)

        def _emit_one(center_expr: str, indent: str) -> None:
            if profile["kind"] == "rect":
                width_expr = (
                    profile["width"]
                    if isinstance(profile["width"], str)
                    else fmt_num(profile["width"])
                )
                height_expr = (
                    profile["height"]
                    if isinstance(profile["height"], str)
                    else fmt_num(profile["height"])
                )
                half_w = f"({width_expr} / 2.0)"
                half_h = f"({height_expr} / 2.0)"
                ux, uy, uz = u_dir
                vx, vy, vz = v_dir
                corners = []
                for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    corners.append(
                        f"({center_expr}[0] + ({half_w}) * ({fmt_num(ux)}) * ({su}) + ({half_h}) * ({fmt_num(vx)}) * ({sv}), "
                        f"{center_expr}[1] + ({half_w}) * ({fmt_num(uy)}) * ({su}) + ({half_h}) * ({fmt_num(vy)}) * ({sv}), "
                        f"{center_expr}[2] + ({half_w}) * ({fmt_num(uz)}) * ({su}) + ({half_h}) * ({fmt_num(vz)}) * ({sv}))"
                    )
                self.state.lines.extend(
                    [
                        f"{indent}_wire = scad.make_polyline_rwire(",
                        f"{indent}    points=[",
                        f"{indent}    {corners[0]},",
                        f"{indent}    {corners[1]},",
                        f"{indent}    {corners[2]},",
                        f"{indent}    {corners[3]},",
                        f"{indent}    ],",
                        f"{indent}    closed=True,",
                        f"{indent})",
                        f"{indent}_profile = scad.make_face_from_wire_rface(wire=_wire)",
                        f"{indent}_solid = scad.extrude_rsolid("
                        f"profile=_profile, direction={fmt_vec(direction)}, "
                        f"distance={dist},)",
                        f"{indent}{body} = scad.union_rsolid({body}, _solid)",
                    ]
                )
            elif profile["kind"] == "circle":
                self.state.lines.extend(
                    [
                        f"{indent}_profile = scad.make_circle_rface("
                        f"center={center_expr}, radius={fmt_num(profile['radius'])}, "
                        f"normal={fmt_vec(normal)},)",
                        f"{indent}_solid = scad.extrude_rsolid("
                        f"profile=_profile, direction={fmt_vec(direction)}, "
                        f"distance={dist},)",
                        f"{indent}{body} = scad.union_rsolid({body}, _solid)",
                    ]
                )
            else:
                self.state.unsupported.append(
                    f"pattern extrude unsupported profile kind {profile['kind']}"
                )

        if "points" in pattern:
            self.state.lines.append("    for _pt in [")
            for point in pattern["points"]:
                local = (
                    float(point[0]),
                    float(point[1]),
                    float(point[2]) if len(point) >= 3 else 0.0,
                )
                self.state.lines.append(f"        {fmt_vec(self._global_point(local))},")
            self.state.lines.append("    ]:")
            _emit_one("_pt", "        ")
            self._sync_body()
            return

        x_count = int(pattern["x_count"])
        y_count = int(pattern["y_count"])
        x_spacing = float(pattern["x_spacing"])
        y_spacing = float(pattern["y_spacing"])
        self.state.lines.append(f"    for _ix in range({x_count}):")
        self.state.lines.append(f"        for _iy in range({y_count}):")
        self.state.lines.append(
            f"            _ox = (_ix - ({x_count} - 1) / 2.0) * {fmt_num(x_spacing)}"
        )
        self.state.lines.append(
            f"            _oy = (_iy - ({y_count} - 1) / 2.0) * {fmt_num(y_spacing)}"
        )
        origin_expr = (
            f"({fmt_num(base_origin[0])} + _ox * {fmt_num(u_dir[0])} + _oy * {fmt_num(v_dir[0])}, "
            f"{fmt_num(base_origin[1])} + _ox * {fmt_num(u_dir[1])} + _oy * {fmt_num(v_dir[1])}, "
            f"{fmt_num(base_origin[2])} + _ox * {fmt_num(u_dir[2])} + _oy * {fmt_num(v_dir[2])})"
        )
        _emit_one(origin_expr, "            ")
        self._sync_body()

    def _op_revolve(self, step: TraceStep) -> None:
        if self.state.pending_profile is None:
            self.state.unsupported.append("revolve without pending profile")
            return
        profile = self._finalize_wire_profile()
        # CadQuery revolve axisStart/axisEnd are workplane-local (toWorldCoords).
        raw_start = step.args[1] if len(step.args) >= 2 else (0.0, 0.0, 0.0)
        raw_end = step.args[2] if len(step.args) >= 3 else (0.0, 1.0, 0.0)
        if isinstance(raw_start, (list, tuple)) and len(raw_start) == 2:
            axis_start = self._global_point((float(raw_start[0]), float(raw_start[1]), 0.0))
        else:
            axis_start = self._global_point(_as_vec3(raw_start))
        if isinstance(raw_end, (list, tuple)) and len(raw_end) == 2:
            axis_end = self._global_point((float(raw_end[0]), float(raw_end[1]), 0.0))
        else:
            axis_end = self._global_point(_as_vec3(raw_end))
        axis = (
            axis_end[0] - axis_start[0],
            axis_end[1] - axis_start[1],
            axis_end[2] - axis_start[2],
        )
        if axis == (0.0, 0.0, 0.0):
            self.state.unsupported.append("revolve with zero-length axis")
            return
        angle = float(step.args[0])
        self._feature("revolve", slug="revolve", kind="Revolve", trace_op="revolve")
        angle_expr = self._param("revolve_angle", angle, comment="revolve angle")
        var = self._assign_body_var()
        profile_lines, profile_expr = _emit_profile_expr(profile, var)
        self.state.lines.extend(profile_lines)
        self.state.lines.append(
            f"    {var} = scad.revolve_rsolid("
            f"profile={profile_expr}, axis={fmt_vec(axis)}, "
            f"angle={angle_expr}, origin={fmt_vec(axis_start)},)"
        )
        self._union_into_body(var)
        self.state.pending_profile = None

    def _op_loft(self, step: TraceStep) -> None:
        profiles = list(self.state.loft_profiles)
        if self.state.pending_profile:
            profiles.append(self._finalize_wire_profile())
        if len(profiles) < 2:
            self.state.unsupported.append("loft requires at least two profiles")
            return
        self._feature("loft", slug="loft", kind="Loft", trace_op="loft")
        var = self._assign_body_var()
        profile_vars: List[str] = []
        for idx, profile in enumerate(profiles):
            prefix = f"{var}_p{idx}"
            profile_lines, profile_var = _emit_profile_expr(profile, prefix, as_wire=True)
            self.state.lines.extend(profile_lines)
            profile_vars.append(profile_var)
        profiles_arg = ", ".join(profile_vars)
        self.state.lines.append(f"    {var} = scad.loft_rsolid(profiles=[{profiles_arg}],)")
        self._union_into_body(var)
        self.state.loft_profiles = []
        self.state.pending_profile = None

    def _emit_profile_cut(self, depth: float, *, feature: str) -> None:
        if self.state.pending_profile is None:
            self.state.unsupported.append(f"{feature} without pending profile")
            return
        self._ensure_fused_body()
        profile = self._finalize_wire_profile()
        body = self.state.body
        if self.state.on_face_workplane:
            profile = dict(profile)
            profile["frame"] = {
                **profile.get("frame", self._plane_frame()),
                "normal": self._profile_normal(),
                "extrude": self._cut_direction(),
            }
        if self.state.pending_rarray:
            self._emit_pattern_cut(profile, depth, feature=feature)
            self.state.pending_profile = None
            self.state.pending_rarray = None
            self._sync_body()
            return
        trace_op = "cutBlind" if feature == "blind cut" else "cutThruAll" if feature == "through cut" else "cut"
        self._feature(feature, slug=feature.replace(" ", "_"), kind="Cut", trace_op=trace_op)
        if depth < 999.0:
            self._param("cut_depth", depth, comment="cut depth")
        self.state.lines.extend(_emit_cut_tool(profile, self.state.plane, depth, "cut"))
        self.state.lines.append(f"    {body} = scad.cut_rsolid({body}, cut_tool)")
        self.state.pending_profile = None
        self._sync_body()

    def _emit_pattern_cut(self, profile: Dict[str, Any], depth: float, *, feature: str) -> None:
        pattern = self.state.pending_rarray or {}
        body = self.state.body
        self._feature(feature, slug=feature.replace(" ", "_"), kind="Cut", trace_op="cutThruAll")
        if "points" in pattern:
            frame = self._plane_frame()
            normal = frame["normal"]
            extrude = self._cut_direction() if self.state.on_face_workplane else frame["extrude"]
            if profile["kind"] not in {"circle", "rect"}:
                self.state.unsupported.append(
                    f"pushPoints cut unsupported profile kind {profile['kind']}"
                )
                return
            self.state.lines.append(f"    {body} = {body}")
            self.state.lines.append("    for _pt in [")
            for point in pattern["points"]:
                local = (
                    float(point[0]),
                    float(point[1]),
                    float(point[2]) if len(point) >= 3 else 0.0,
                )
                global_pt = self._global_point(local)
                self.state.lines.append(f"        {fmt_vec(global_pt)},")
            self.state.lines.append("    ]:")
            if profile["kind"] == "circle":
                self.state.lines.extend(
                    [
                        f"        _profile = scad.make_circle_rface("
                        f"center=_pt, radius={fmt_num(profile['radius'])}, "
                        f"normal={fmt_vec(normal)},)",
                        f"        _tool = scad.extrude_rsolid("
                        f"profile=_profile, direction={fmt_vec(extrude)}, "
                        f"distance={fmt_num(depth)},)",
                        f"        {body} = scad.cut_rsolid({body}, _tool)",
                    ]
                )
            elif profile["kind"] == "rect":
                half_w = (
                    f"({profile['width']} / 2.0)"
                    if isinstance(profile["width"], str)
                    else f"({fmt_num(profile['width'])} / 2.0)"
                )
                half_h = (
                    f"({profile['height']} / 2.0)"
                    if isinstance(profile["height"], str)
                    else f"({fmt_num(profile['height'])} / 2.0)"
                )
                ux, uy, uz = self.state.u_dir
                vx, vy, vz = self.state.v_dir
                corners = []
                for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    corners.append(
                        f"(_pt[0] + ({half_w}) * ({fmt_num(ux)}) * ({su}) + ({half_h}) * ({fmt_num(vx)}) * ({sv}), "
                        f"_pt[1] + ({half_w}) * ({fmt_num(uy)}) * ({su}) + ({half_h}) * ({fmt_num(vy)}) * ({sv}), "
                        f"_pt[2] + ({half_w}) * ({fmt_num(uz)}) * ({su}) + ({half_h}) * ({fmt_num(vz)}) * ({sv}))"
                    )
                self.state.lines.extend(
                    [
                        "        _wire = scad.make_polyline_rwire(",
                        "            points=[",
                        f"            {corners[0]},",
                        f"            {corners[1]},",
                        f"            {corners[2]},",
                        f"            {corners[3]},",
                        "            ],",
                        "            closed=True,",
                        "        )",
                        "        _profile = scad.make_face_from_wire_rface(wire=_wire)",
                        f"        _tool = scad.extrude_rsolid("
                        f"profile=_profile, direction={fmt_vec(extrude)}, "
                        f"distance={fmt_num(depth)},)",
                        f"        {body} = scad.cut_rsolid({body}, _tool)",
                    ]
                )
            else:
                self.state.unsupported.append(
                    f"pushPoints cut unsupported profile kind {profile['kind']}"
                )
            return

        if "x_count" in pattern:
            x_count = int(pattern["x_count"])
            y_count = int(pattern["y_count"])
            x_spacing = float(pattern["x_spacing"])
            y_spacing = float(pattern["y_spacing"])
            u_dir = self.state.u_dir
            v_dir = self.state.v_dir
            frame = self._plane_frame()
            cut_dir = self._cut_direction() if self.state.on_face_workplane else frame["extrude"]
            base_origin = profile.get("origin", self.state.origin)
            self.state.lines.append(f"    {body} = {body}")
            self.state.lines.append(f"    for _ix in range({x_count}):")
            self.state.lines.append(f"        for _iy in range({y_count}):")
            self.state.lines.append(
                f"            _ox = (_ix - ({x_count} - 1) / 2.0) * {fmt_num(x_spacing)}"
            )
            self.state.lines.append(
                f"            _oy = (_iy - ({y_count} - 1) / 2.0) * {fmt_num(y_spacing)}"
            )
            origin_expr = (
                f"({fmt_num(base_origin[0])} + _ox * {fmt_num(u_dir[0])} + _oy * {fmt_num(v_dir[0])}, "
                f"{fmt_num(base_origin[1])} + _ox * {fmt_num(u_dir[1])} + _oy * {fmt_num(v_dir[1])}, "
                f"{fmt_num(base_origin[2])} + _ox * {fmt_num(u_dir[2])} + _oy * {fmt_num(v_dir[2])})"
            )
            if profile["kind"] == "rect":
                self.state.lines.extend(
                    [
                        f"            with scad.SimpleWorkplane("
                        f"origin={origin_expr}, normal={fmt_vec(frame['normal'])}, "
                        f"x_dir={fmt_vec(u_dir)},):",
                        f"                _profile = scad.make_rectangle_rface("
                        f"width={fmt_num(profile['width'])}, height={fmt_num(profile['height'])}, "
                        f"center=(0, 0, 0), normal=(0, 0, 1),)",
                        f"            _tool = scad.extrude_rsolid("
                        f"profile=_profile, direction={fmt_vec(cut_dir)}, "
                        f"distance={fmt_num(depth)},)",
                        f"            {body} = scad.cut_rsolid({body}, _tool)",
                    ]
                )
            elif profile["kind"] == "circle":
                self.state.lines.extend(
                    [
                        f"            _profile = scad.make_circle_rface("
                        f"center={origin_expr}, radius={fmt_num(profile['radius'])}, "
                        f"normal={fmt_vec(frame['normal'])},)",
                        f"            _tool = scad.extrude_rsolid("
                        f"profile=_profile, direction={fmt_vec(cut_dir)}, "
                        f"distance={fmt_num(depth)},)",
                        f"            {body} = scad.cut_rsolid({body}, _tool)",
                    ]
                )
            else:
                self.state.unsupported.append(f"pattern cut unsupported profile kind {profile['kind']}")
            return

        self.state.unsupported.append("pattern cut without rarray or pushPoints")

    def _op_hole(self, step: TraceStep) -> None:
        self._ensure_fused_body()
        depth = step.kwargs.get("depth")
        if depth is None and len(step.args) >= 2:
            depth = step.args[1]
        blind = depth is not None
        self._feature(
            "blind hole" if blind else "through hole",
            slug="hole",
            kind="Hole",
            trace_op="hole",
        )
        diameter = self._param("hole_diameter", float(step.args[0]), comment="hole diameter")
        radius_expr = f"({diameter} / 2.0)"
        hole_depth = float(depth) if depth is not None else 1000.0
        depth_expr = (
            self._param("hole_depth", hole_depth, comment="hole depth")
            if blind
            else fmt_num(hole_depth)
        )
        normal = self._profile_normal()
        hole_dir = self._hole_extrude_direction(normal)
        body = self.state.body
        tag = self._tag()
        pattern = self.state.pending_rarray or {}
        centers: List[str]
        if "points" in pattern:
            centers = []
            for point in pattern["points"]:
                local = (
                    float(point[0]),
                    float(point[1]),
                    float(point[2]) if len(point) >= 3 else 0.0,
                )
                centers.append(fmt_vec(self._global_point(local)))
            self.state.pending_rarray = None
        else:
            centers = [fmt_vec(self.state.origin)]
            self.state.pending_rarray = None
        if len(centers) > 1:
            self.state.lines.append(f"    {body} = {body}")
            self.state.lines.append("    for _pt in [")
            for center in centers:
                self.state.lines.append(f"        {center},")
            self.state.lines.append("    ]:")
            indent = "        "
            center_expr = "_pt"
        else:
            indent = "    "
            center_expr = centers[0]
        self.state.lines.extend(
            [
                f"{indent}_hole_profile = scad.make_circle_rface("
                f"center={center_expr}, radius={radius_expr}, normal={fmt_vec(normal)},)",
                f"{indent}_hole_tool = scad.extrude_rsolid("
                f"profile=_hole_profile, direction={fmt_vec(hole_dir)}, distance={depth_expr},)",
                f"{indent}{body} = scad.cut_rsolid({body}, _hole_tool)",
            ]
        )
        if len(centers) == 1:
            self.state.lines.append(f"    # feature commit: {tag}")
        else:
            self.state.lines.append(f"    # feature commit: {tag}")
        self._sync_body()

    def _op_cskHole(self, step: TraceStep) -> None:
        """CadQuery countersink hole: through/blind bore + conical countersink."""
        self._ensure_fused_body()
        if len(step.args) < 3:
            self.state.unsupported.append("cskHole requires diameter, cskDiameter, cskAngle")
            return
        diameter = float(step.args[0])
        csk_diameter = float(step.args[1])
        csk_angle = float(step.args[2])
        depth = step.kwargs.get("depth")
        self._feature("countersink hole", slug="csk_hole", kind="Hole", trace_op="cskHole")
        dia_expr = self._param("hole_diameter", diameter, comment="hole diameter")
        csk_dia_expr = self._param("csk_diameter", csk_diameter, comment="countersink diameter")
        csk_angle_expr = self._param("csk_angle", csk_angle, comment="countersink included angle")
        hole_r = f"(({dia_expr}) / 2.0)"
        csk_r = f"(({csk_dia_expr}) / 2.0)"
        # depth of cone: (R_csk - R_hole) / tan(half_angle)
        csk_depth = (
            f"(({csk_r}) - ({hole_r})) / math.tan(math.radians(({csk_angle_expr}) / 2.0))"
        )
        hole_depth = float(depth) if depth is not None else 1000.0
        depth_expr = (
            self._param("hole_depth", hole_depth, comment="hole depth")
            if depth is not None
            else fmt_num(hole_depth)
        )
        normal = self._profile_normal()
        hole_dir = self._hole_extrude_direction(normal)
        body = self.state.body
        pattern = self.state.pending_rarray or {}
        centers: List[Tuple[float, float, float]] = []
        if "points" in pattern:
            for point in pattern["points"]:
                local = (
                    float(point[0]),
                    float(point[1]),
                    float(point[2]) if len(point) >= 3 else 0.0,
                )
                centers.append(self._global_point(local))
            self.state.pending_rarray = None
        else:
            centers = [self.state.origin]
            self.state.pending_rarray = None

        for index, center in enumerate(centers):
            prefix = f"_csk{index}"
            end_center = (
                f"({fmt_num(center[0])} + ({csk_depth}) * {fmt_num(hole_dir[0])}, "
                f"{fmt_num(center[1])} + ({csk_depth}) * {fmt_num(hole_dir[1])}, "
                f"{fmt_num(center[2])} + ({csk_depth}) * {fmt_num(hole_dir[2])})"
            )
            self.state.lines.extend(
                [
                    f"    {prefix}_bore = scad.make_circle_rface("
                    f"center={fmt_vec(center)}, radius={hole_r}, normal={fmt_vec(normal)},)",
                    f"    {prefix}_bore_tool = scad.extrude_rsolid("
                    f"profile={prefix}_bore, direction={fmt_vec(hole_dir)}, distance={depth_expr},)",
                    f"    {body} = scad.cut_rsolid({body}, {prefix}_bore_tool)",
                    f"    {prefix}_p0 = scad.make_circle_rwire("
                    f"center={fmt_vec(center)}, radius={csk_r}, normal={fmt_vec(normal)},)",
                    f"    {prefix}_p1 = scad.make_circle_rwire("
                    f"center={end_center}, radius={hole_r}, normal={fmt_vec(normal)},)",
                    f"    {prefix}_csk = scad.loft_rsolid(profiles=[{prefix}_p0, {prefix}_p1],)",
                    f"    {body} = scad.cut_rsolid({body}, {prefix}_csk)",
                ]
            )
        self.state.lines.append(f"    # feature commit: {self._tag()}")
        self._sync_body()

    def _op_cutBlind(self, step: TraceStep) -> None:
        depth = abs(float(step.args[0]))
        self._emit_profile_cut(depth, feature="blind cut")

    def _op_cutThruAll(self, step: TraceStep) -> None:
        self._emit_profile_cut(1000.0, feature="through cut")

    def _op_cut(self, step: TraceStep) -> None:
        if step.args and _is_workplane_ref(step.args[0]):
            return
        tool = self.state.last_solid
        if tool is None or tool == self.state.body:
            self.state.unsupported.append("cut without distinct tool solid")
            return
        self._apply_boolean("cut", tool)

    def _op_union(self, step: TraceStep) -> None:
        if step.args and _is_workplane_ref(step.args[0]):
            return
        tool = self.state.last_solid
        if tool is None or tool == self.state.body:
            self.state.unsupported.append("union without distinct tool solid")
            return
        self._apply_boolean("union", tool)

    def _op_intersect(self, step: TraceStep) -> None:
        if step.args and _is_workplane_ref(step.args[0]):
            return
        tool = self.state.last_solid
        if tool is None or tool == self.state.body:
            self.state.unsupported.append("intersect without distinct tool solid")
            return
        self._apply_boolean("intersect", tool)

    def _op_shell(self, step: TraceStep) -> None:
        if not self.state.has_body:
            self.state.unsupported.append("shell without body")
            return
        self._ensure_fused_body()
        thickness = abs(float(step.args[0]))
        body = self.state.body
        faces, uses_ql = _resolve_faces(body, self.state.pending_face_selector)
        if uses_ql:
            self.state.uses_ql = True
        self._feature("shell", slug="shell", kind="Shell", trace_op="shell")
        thickness_expr = self._param("shell_thickness", thickness, comment="shell wall thickness")
        self.state.lines.append(
            f"    {body} = scad.shell_rsolid("
            f"solid={body}, faces_to_remove={faces}, "
            f"thickness={thickness_expr}, result_tag={self._tag()!r},)"
        )
        self.state.pending_face_selector = None
        self._sync_body()

    def _op_chamfer(self, step: TraceStep) -> None:
        self._ensure_fused_body()
        self._feature("chamfer", slug="chamfer", kind="Chamfer", trace_op="chamfer")
        distance = self._param("chamfer_distance", float(step.args[0]), comment="chamfer distance")
        body = self.state.body
        edges, uses_ql = _resolve_edges(
            body,
            step,
            uses_ql=self.state.uses_ql,
            pending_edge_selector=self.state.pending_edge_selector,
            pending_face_selector=self.state.pending_face_selector,
        )
        if uses_ql:
            self.state.uses_ql = True
        self.state.lines.append(
            f"    {body} = scad.chamfer_rsolid(solid={body}, edges={edges}, "
            f"distance={distance}, result_tag={self._tag()!r},)"
        )
        self.state.pending_edge_selector = None
        self.state.pending_face_selector = None
        self._sync_body()

    def _op_fillet(self, step: TraceStep) -> None:
        self._ensure_fused_body()
        self._feature("fillet", slug="fillet", kind="Fillet", trace_op="fillet")
        radius = self._param("fillet_radius", float(step.args[0]), comment="fillet radius")
        body = self.state.body
        edges, uses_ql = _resolve_edges(
            body,
            step,
            uses_ql=self.state.uses_ql,
            pending_edge_selector=self.state.pending_edge_selector,
            pending_face_selector=self.state.pending_face_selector,
        )
        if uses_ql:
            self.state.uses_ql = True
        self.state.lines.append(
            f"    {body} = scad.fillet_rsolid(solid={body}, edges={edges}, "
            f"radius={radius}, result_tag={self._tag()!r},)"
        )
        self.state.pending_edge_selector = None
        self.state.pending_face_selector = None
        self._sync_body()

    def _op_faces(self, step: TraceStep) -> None:
        if step.selector:
            self.state.pending_face_selector = str(step.selector)
            # Face selection replaces any prior edge selection.
            self.state.pending_edge_selector = None
        return

    def _op_edges(self, step: TraceStep) -> None:
        if step.selector:
            self.state.pending_edge_selector = str(step.selector)
            self.state.pending_face_selector = None
        return

    def _emit_module(self) -> str:
        return emit_sftc_module(
            graph_id=self.graph_id,
            header=f"SFTC model traced from CadQuery: {self.graph_id}",
            parameters=self.parameters,
            feature_lines=self.state.lines,
            unsupported=self.state.unsupported,
            body=self.state.body if self.state.has_body else None,
            include_ql_import=self.state.uses_ql,
        )


def replay_trace_to_sftc(trace: OperationTrace, *, graph_id: str) -> Tuple[str, Dict[str, Any]]:
    return TraceReplayer(graph_id).replay(trace)
