"""Replay CadQuery traces into FTC source (bodies dataflow, sketch profiles).

The state machine (plane frames, pending profiles, pattern grids, tool chains)
is ported from the upstream converter; every emission site is rewritten to the
current FTC conventions:

- blocks open with ``# ---- feature: <slug> (<role>[, profile=geometry]) ----``
  and rebind the ``bodies`` list (histjson-translator shapes: per-body union
  loop for adds, list comprehension for subtracts, guarded loop for modifies);
- planar profiles are authored through the sketch API in local coordinates,
  annotated ``profile=geometry`` (transcribed data, constraints unknown);
- fillet/chamfer/shell selections are QL predicates synthesized from trace
  fingerprints with cardinality, never topology enumeration;
- through-cut depths derive from the trace bounding box, not magic numbers.

The translator only translates: unsupported trace content is recorded as notes
and left for the external validator to reconcile.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .emit import (
    SketchScript,
    SlugAllocator,
    block_header,
    emit_module,
    emit_profile_sketch,
    emit_ql_edges_selector,
    emit_ql_faces_selector,
    fmt_num,
    fmt_vec,
)
from .op_map import FTC_ROLE, FTC_SLUG
from .tracer.trace_schema import GeoFingerprint, OperationTrace, TraceStep

Vec3 = Tuple[float, float, float]

# CadQuery named planes (fallback only — the tracer records the live frame).
PLANE_TABLE: Dict[str, Dict[str, Vec3]] = {
    "XY": {"normal": (0.0, 0.0, 1.0), "u": (1.0, 0.0, 0.0), "v": (0.0, 1.0, 0.0)},
    "XZ": {"normal": (0.0, -1.0, 0.0), "u": (1.0, 0.0, 0.0), "v": (0.0, 0.0, 1.0)},
    "YZ": {"normal": (1.0, 0.0, 0.0), "u": (0.0, 1.0, 0.0), "v": (0.0, 0.0, 1.0)},
}

_PROFILE_KINDS_FOR_TOOL = {"circle", "rect", "wire_path", "spline_path"}


def _as_vec3(value: Any) -> Vec3:
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    raise ValueError(f"expected 3-vector, got {value!r}")


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _local_to_global(
    origin: Vec3,
    u_dir: Vec3,
    v_dir: Vec3,
    local: Tuple[float, float, float],
    *,
    normal: Optional[Vec3] = None,
) -> Vec3:
    nx, ny, nz = normal if normal is not None else (0.0, 0.0, 0.0)
    lz = float(local[2]) if len(local) >= 3 else 0.0
    return (
        origin[0] + local[0] * u_dir[0] + local[1] * v_dir[0] + lz * nx,
        origin[1] + local[0] * u_dir[1] + local[1] * v_dir[1] + lz * ny,
        origin[2] + local[0] * u_dir[2] + local[1] * v_dir[2] + lz * nz,
    )


def _global_to_local(origin: Vec3, u_dir: Vec3, v_dir: Vec3, point: Vec3) -> Tuple[float, float]:
    delta = (point[0] - origin[0], point[1] - origin[1], point[2] - origin[2])
    return (_dot(delta, u_dir), _dot(delta, v_dir))


def _project_to_plane(point: Vec3, origin: Vec3, normal: Vec3) -> Vec3:
    """Drop floating-point drift so world-space wires stay coplanar."""
    nn = math.sqrt(normal[0] ** 2 + normal[1] ** 2 + normal[2] ** 2)
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


def _is_named_workplane(plane_name: Optional[str]) -> bool:
    if not plane_name:
        return False
    return str(plane_name) in PLANE_TABLE or str(plane_name).startswith("Plane(")


def _is_workplane_ref(value: Any) -> bool:
    return isinstance(value, dict) and value.get("__workplane_ref__") is True


def _find_path_chain_range(steps: List[TraceStep], end_index: int) -> Tuple[int, int]:
    start = end_index - 1
    while start >= 0:
        if steps[start].op == "Workplane" and _is_named_workplane(steps[start].plane_name):
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
    """Drop only unnamed Workplane constructors (pure navigation noise).

    Everything else flows into the replay loop: ops the replayer understands
    become features, ops it does not understand become unsupported notes —
    nothing is silently dropped.
    """
    filtered: List[TraceStep] = []
    for step in steps:
        if step.op == "Workplane":
            if _is_named_workplane(step.plane_name):
                filtered.append(step)
            continue
        filtered.append(step)
    return filtered


@dataclass
class ReplayState:
    plane: str = "XY"
    origin: Vec3 = (0.0, 0.0, 0.0)
    normal: Vec3 = (0.0, 0.0, 1.0)
    u_dir: Vec3 = (1.0, 0.0, 0.0)
    v_dir: Vec3 = (0.0, 1.0, 0.0)
    pending_profile: Optional[Dict[str, Any]] = None
    loft_profiles: List[Dict[str, Any]] = field(default_factory=list)
    pending_rarray: Optional[Dict[str, Any]] = None
    pending_edge_selector: Optional[str] = None
    pending_edge_selections: List[GeoFingerprint] = field(default_factory=list)
    pending_face_selector: Optional[str] = None
    pending_face_selections: List[GeoFingerprint] = field(default_factory=list)
    on_face_workplane: bool = False
    lines: List[str] = field(default_factory=list)
    unsupported: List[str] = field(default_factory=list)
    bodies: List[str] = field(default_factory=list)
    last_solid: Optional[str] = None
    uses_ql: bool = False


class TraceReplayer:
    """Single-pass trace interpreter emitting FTC source."""

    def __init__(
        self,
        stem: str,
        *,
        tool_mode: bool = False,
        tool_prefix: str = "tool",
        cq_bbox: Optional[List[float]] = None,
    ) -> None:
        self.stem = stem
        self.state = ReplayState()
        self._tool_mode = tool_mode
        self._tool_prefix = tool_prefix
        self._tool_serial = 0
        self._slug_tool_counts: Dict[str, int] = {}
        self._cq_bbox = cq_bbox
        self._slugs = SlugAllocator()
        self.features: List[Dict[str, str]] = []
        self.built_profile = False  # tool chains: did this tool build 2D input?

    # ------------------------------------------------------------------
    # block bookkeeping

    def _open_block(self, op: str, *, role: Optional[str] = None, tiers: Sequence = ()) -> str:
        """Open an FTC block; returns the deduped slug (underscored var base)."""
        slug = self._slugs.allocate(FTC_SLUG.get(op, op))
        resolved_role = role or FTC_ROLE.get(op, "build")
        if resolved_role == "build" and (self.state.bodies or self._tool_mode):
            if not self._tool_mode:
                resolved_role = "add"
        if self._tool_mode:
            return slug.replace("-", "_")
        self.state.lines.append("    " + block_header(slug, resolved_role, tiers=list(tiers)))
        self.features.append({"slug": slug, "role": resolved_role, "op": op})
        return slug.replace("-", "_")

    def _tool_var(self, slug_base: str) -> str:
        self._tool_serial += 1
        if self._tool_mode:
            return f"{self._tool_prefix}_{self._tool_serial}"
        per_slug = self._slug_tool_counts.get(slug_base, 0) + 1
        self._slug_tool_counts[slug_base] = per_slug
        return f"{slug_base}_tool" if per_slug == 1 else f"{slug_base}_tool{per_slug}"

    def _thru_depth(self, direction: Vec3) -> float:
        """Through-cut length from the trace bbox along the cut direction."""
        if self._cq_bbox is None:
            return 1000.0
        lo = self._cq_bbox[:3]
        hi = self._cq_bbox[3:]
        extent = max(hi[i] - lo[i] for i in range(3))
        span = sum(abs(direction[i]) * (hi[i] - lo[i]) for i in range(3))
        return span + 0.2 * extent + 2.0

    # ------------------------------------------------------------------
    # body commits (histjson shapes)

    def _commit_first(self, var: str) -> None:
        self.state.bodies = [var]
        self.state.lines.append(f"    bodies = list([{var}])")

    def _commit_add(self, var: str) -> None:
        if not self.state.bodies:
            self._commit_first(var)
            return
        self.state.lines.extend(
            [
                "    _merged = False",
                "    _next = []",
                "    for _b in bodies:",
                "        try:",
                f"            _next.append(scad.union_rsolid(_b, [{var}]))",
                "            _merged = True",
                "        except Exception:",
                "            _next.append(_b)",
                "    bodies = _next",
                "    if not _merged:",
                f"        bodies.extend([{var}])",
            ]
        )
        # Which unions actually fused is a runtime fact; one placeholder keeps
        # downstream role decisions ("body exists") sound.
        self.state.bodies = [self.state.bodies[0]] if self.state.bodies else []

    def _commit_cut(self, tools: List[str]) -> None:
        tool_args = ", ".join(tools)
        self.state.lines.append(f"    bodies = [scad.cut_rsolid(_b, [{tool_args}]) for _b in bodies]")
        self.state.bodies = [self.state.bodies[0]] if self.state.bodies else []

    def _commit_intersect(self, tool: str) -> None:
        self.state.lines.append(f"    bodies = [scad.intersect_rsolid(_b, [{tool}]) for _b in bodies]")
        self.state.bodies = [self.state.bodies[0]] if self.state.bodies else []

    def _commit_modify(self, call_template: str) -> None:
        """Guarded per-body modify loop; bodies without a match stay as-is."""
        self.state.lines.extend(
            [
                "    _next = []",
                "    for _b in bodies:",
                "        try:",
                f"            _next.append({call_template})",
                "        except Exception:",
                "            _next.append(_b)",
                "    bodies = _next",
            ]
        )

    # ------------------------------------------------------------------
    # plane frame tracking (ported)

    def _update_plane_frame(self, step: TraceStep) -> None:
        if step.op == "Workplane":
            if step.plane_name in PLANE_TABLE:
                self.state.plane = step.plane_name
                if step.plane_normal and step.plane_x_dir:
                    normal = _as_vec3(step.plane_normal)
                    u_dir = _as_vec3(step.plane_x_dir)
                    self.state.normal = normal
                    self.state.u_dir = u_dir
                    self.state.v_dir = _cross(normal, u_dir)
                else:
                    frame = PLANE_TABLE[self.state.plane]
                    self.state.normal = frame["normal"]
                    self.state.u_dir = frame["u"]
                    self.state.v_dir = frame["v"]
                if step.plane_origin and len(step.plane_origin) >= 3:
                    self.state.origin = _as_vec3(step.plane_origin)
            elif step.plane_name and str(step.plane_name).startswith("Plane("):
                if step.plane_origin and len(step.plane_origin) >= 3:
                    self.state.origin = _as_vec3(step.plane_origin)
                if step.plane_normal and step.plane_x_dir:
                    normal = _as_vec3(step.plane_normal)
                    u_dir = _as_vec3(step.plane_x_dir)
                    self.state.normal = normal
                    self.state.u_dir = u_dir
                    self.state.v_dir = _cross(normal, u_dir)
            return

        if step.plane_origin and len(step.plane_origin) >= 3:
            self.state.origin = _as_vec3(step.plane_origin)
        if step.plane_normal and step.plane_x_dir:
            normal = _as_vec3(step.plane_normal)
            u_dir = _as_vec3(step.plane_x_dir)
            self.state.normal = normal
            self.state.u_dir = u_dir
            self.state.v_dir = _cross(normal, u_dir)

    def _global_point(self, local: Tuple[float, float, float]) -> Vec3:
        return _local_to_global(
            self.state.origin,
            self.state.u_dir,
            self.state.v_dir,
            local,
            normal=self.state.normal,
        )

    def _mirror_point_about_local_axis(self, point: Vec3, *, axis: str) -> Vec3:
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

    def _extrude_direction(self) -> Vec3:
        return self.state.normal

    def _negated_normal(self) -> Vec3:
        n = self.state.normal
        return (-n[0], -n[1], -n[2])

    def _hole_direction(self) -> Vec3:
        if self.state.on_face_workplane:
            return self._negated_normal()
        return self.state.normal

    def _cut_direction(self) -> Vec3:
        if self.state.on_face_workplane:
            return self._negated_normal()
        return self.state.normal

    def _plane_frame(self) -> Dict[str, Vec3]:
        return {
            "normal": self.state.normal,
            "extrude": self.state.normal,
            "u": self.state.u_dir,
            "v": self.state.v_dir,
        }

    def _attach_frame(self, profile: Dict[str, Any]) -> Dict[str, Any]:
        enriched = dict(profile)
        enriched["frame"] = self._plane_frame()
        if "origin" not in profile:
            enriched["origin"] = self.state.origin
        return enriched

    # ------------------------------------------------------------------
    # profile accumulation (ported)

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
            if segment.get("mid") is not None:
                cleaned["mid"] = _project_to_plane(segment["mid"], origin, normal)
            segments.append(cleaned)
        return self._attach_frame(
            {
                "kind": "wire_path",
                "plane": self.state.plane,
                "origin": origin,
                "segments": segments,
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
        start: Vec3,
        end: Vec3,
        mid: Optional[Vec3] = None,
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

    def _emit_profile(self, var: str, profile: Dict[str, Any], *, as_wire: bool = False) -> str:
        lines, expr, notes = emit_profile_sketch(profile, var, as_wire=as_wire)
        self.state.lines.extend(lines)
        self.state.unsupported.extend(notes)
        return expr

    def _profile_is_sketch_tier(self, profile: Dict[str, Any]) -> bool:
        return profile.get("kind") in {"circle", "rect", "wire_path"}

    # ------------------------------------------------------------------
    # replay driver

    def replay(self, trace: OperationTrace) -> Tuple[str, Dict[str, Any]]:
        steps = filter_meaningful_steps(trace.steps)
        meta: Dict[str, Any] = {
            "unsupported": [],
            "feature_count": 0,
            "features": self.features,
        }
        if not steps:
            meta["status"] = "error"
            meta["error"] = "no meaningful trace steps"
            return self._emit_module(), meta

        consumed: set = set()
        for index, step in enumerate(steps):
            if step.op == "sweep":
                path_arg = step.args[0] if step.args else None
                if isinstance(path_arg, dict) and path_arg.get("__workplane_path__"):
                    start, end = _find_path_chain_range(steps, index)
                    consumed.update(range(start, end))
            if step.op in {"cut", "union", "intersect"} and step.args and _is_workplane_ref(step.args[0]):
                start, end = _find_tool_chain_range(steps, index)
                consumed.update(range(start, end))

        for index, step in enumerate(steps):
            if index in consumed:
                continue
            self._update_plane_frame(step)

            if step.op in {"cut", "union", "intersect"} and step.args and _is_workplane_ref(step.args[0]):
                start, end = _find_tool_chain_range(steps, index)
                try:
                    tool_lines, tool_var, tool_unsupported, tool_built_profile = self._replay_tool_steps(
                        steps[start:end],
                        prefix=f"tool_{index}",
                    )
                    if not tool_var:
                        self.state.unsupported.append(f"{step.op}: tool chain produced no solid")
                    else:
                        # Block header first, then the tool construction, then
                        # the boolean application — one block per feature.
                        self._apply_boolean(step.op, tool_var, built_profile=tool_built_profile)
                        self.state.lines.extend(tool_lines)
                        self.state.unsupported.extend(tool_unsupported)
                        self._finish_boolean(step.op, tool_var)
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

        meta["status"] = "partial" if self.state.unsupported else "ok"
        meta["unsupported"] = list(self.state.unsupported)
        meta["feature_count"] = len(self.features)
        meta["features"] = list(self.features)
        if not self.state.bodies:
            meta["status"] = "error"
            meta["error"] = "no solid produced"
        return self._emit_module(), meta

    def _emit_module(self) -> str:
        return emit_module(
            stem=self.stem,
            feature_lines=self.state.lines,
            uses_ql=self.state.uses_ql,
            has_body=bool(self.state.bodies),
            unsupported=self.state.unsupported,
        )

    # ------------------------------------------------------------------
    # tool chains and booleans

    def _replay_tool_steps(
        self,
        steps: List[TraceStep],
        *,
        prefix: str,
    ) -> Tuple[List[str], str, List[str], bool]:
        sub = TraceReplayer(self.stem, tool_mode=True, tool_prefix=prefix, cq_bbox=self._cq_bbox)
        sub_consumed: set = set()
        for index, step in enumerate(steps):
            if step.op == "sweep":
                path_arg = step.args[0] if step.args else None
                if isinstance(path_arg, dict) and path_arg.get("__workplane_path__"):
                    start, end = _find_path_chain_range(steps, index)
                    sub_consumed.update(range(start, end))
        for index, step in enumerate(steps):
            if index in sub_consumed:
                continue
            sub._update_plane_frame(step)
            handler = getattr(sub, f"_op_{step.op}", None)
            if handler is None:
                sub.state.unsupported.append(f"unsupported op: {step.op}")
                continue
            try:
                handler(step)
            except Exception as exc:
                sub.state.unsupported.append(f"{step.op}: {exc}")
        tool_var = sub.state.last_solid
        if tool_var is None:
            return sub.state.lines, "", list(sub.state.unsupported), sub.built_profile
        return sub.state.lines, tool_var, list(sub.state.unsupported), sub.built_profile

    def _apply_boolean(self, op: str, tool_var: str, *, built_profile: bool = False) -> None:
        """Open the boolean block (header only; tool lines follow, then
        :meth:`_finish_boolean` emits the application)."""
        del tool_var
        tiers = ["profile=geometry"] if built_profile else []
        self._open_block(op, tiers=tiers)

    def _finish_boolean(self, op: str, tool_var: str) -> None:
        if not self.state.bodies:
            # CadQuery boolean with a tool before any base solid: the tool
            # becomes the body (translated as-is, no boolean emitted).
            self._commit_first(tool_var)
            return
        if op == "union":
            self._commit_add(tool_var)
        elif op == "cut":
            self._commit_cut([tool_var])
        else:
            self._commit_intersect(tool_var)
        self.state.last_solid = tool_var

    # ------------------------------------------------------------------
    # sweep

    def _build_path_wire(self, path_steps: List[TraceStep], prefix: str) -> Tuple[List[str], str, bool]:
        sub = TraceReplayer(self.stem, tool_mode=True, tool_prefix=prefix, cq_bbox=self._cq_bbox)
        for step in path_steps:
            sub._update_plane_frame(step)
            handler = getattr(sub, f"_op_{step.op}", None)
            if handler is None:
                continue
            handler(step)
        if sub.state.pending_profile is None:
            raise ValueError("path chain produced no wire profile")
        profile = sub.state.pending_profile
        if profile.get("kind") != "spline_path":
            profile = sub._finalize_wire_profile()
        lines, expr, notes = emit_profile_sketch(profile, prefix, as_wire=True)
        return lines, expr, bool(notes)

    def _op_sweep(self, step: TraceStep, *, path_steps: Optional[List[TraceStep]]) -> None:
        if self.state.pending_profile is None:
            self.state.unsupported.append("sweep without pending profile")
            return
        profile = self._finalize_wire_profile()
        if profile.get("kind") == "wire_path" and not profile.get("closed"):
            self.state.unsupported.append("sweep: open profile wire (SDK sweep needs a closed face)")
            return
        is_frenet = bool(step.kwargs.get("isFrenet", False))
        path_arg = step.args[0] if step.args else None

        helix = None
        if isinstance(path_arg, dict) and path_arg.get("__helix__"):
            helix = path_arg["__helix__"]
        elif not path_steps:
            self.state.unsupported.append("sweep without path")
            return

        tiers = ["profile=geometry"]
        if helix is not None:
            tiers.append("path=geometry")
        elif path_steps is not None:
            tiers.append("path=geometry")
        var_base = self._open_block("sweep", tiers=tiers)
        var = self._tool_var(var_base)
        face_expr = self._emit_profile(var, profile)
        if helix is not None:
            center = _as_vec3(helix.get("center", (0.0, 0.0, 0.0)))
            direction = _as_vec3(helix.get("dir", (0.0, 0.0, 1.0)))
            self.state.lines.append(
                f"    {var}_path = scad.make_helix_rwire("
                f"pitch={fmt_num(float(helix['pitch']))}, "
                f"height={fmt_num(float(helix['height']))}, "
                f"radius={fmt_num(float(helix['radius']))}, "
                f"center={fmt_vec(center)}, dir={fmt_vec(direction)},)"
            )
            path_expr = f"{var}_path"
        else:
            assert path_steps is not None  # narrowed by the `not path_steps` early return
            path_lines, path_expr, path_is_geometry = self._build_path_wire(path_steps, f"{var}_path")
            self.state.lines.extend(path_lines)
            if path_is_geometry:
                self.state.unsupported.append("sweep path: geometry tier (interpolated spline)")
        self.state.lines.append(
            f"    {var} = scad.sweep_rsolid("
            f"profile={face_expr}, path={path_expr}, is_frenet={is_frenet!r},)"
        )
        if self._tool_mode:
            self.state.last_solid = var
        else:
            self._commit_add(var)
        self.state.pending_profile = None

    # ------------------------------------------------------------------
    # context ops (ported)

    def _op_transformed(self, step: TraceStep) -> None:
        if self.state.pending_profile is not None:
            self._stash_profile_for_loft()
        del step

    def _op_workplane(self, step: TraceStep) -> None:
        self._stash_profile_for_loft()
        self.state.on_face_workplane = True
        self.state.pending_face_selector = None
        self.state.pending_face_selections = []
        offset = step.kwargs.get("offset")
        if offset is not None:
            normal = self.state.normal
            delta = float(offset)
            self.state.origin = (
                self.state.origin[0] + normal[0] * delta,
                self.state.origin[1] + normal[1] * delta,
                self.state.origin[2] + normal[2] * delta,
            )
        self._update_plane_frame(step)

    def _op_center(self, step: TraceStep) -> None:
        if len(step.args) >= 2:
            xy = (float(step.args[0]), float(step.args[1]))
        elif step.args:
            value = step.args[0]
            if isinstance(value, (list, tuple)) and len(value) >= 2:
                xy = (float(value[0]), float(value[1]))
            else:
                return
        else:
            return
        self.state.origin = self._global_point((xy[0], xy[1], 0.0))

    def _op_faces(self, step: TraceStep) -> None:
        if step.selector:
            self.state.pending_face_selector = str(step.selector)
            self.state.pending_face_selections = list(step.selections)
            self.state.pending_edge_selector = None
            self.state.pending_edge_selections = []

    def _op_edges(self, step: TraceStep) -> None:
        if step.selector:
            self.state.pending_edge_selector = str(step.selector)
            self.state.pending_edge_selections = list(step.selections)
            self.state.pending_face_selector = None
            self.state.pending_face_selections = []

    def _op_Workplane(self, step: TraceStep) -> None:
        if step.plane_name in PLANE_TABLE:
            self.state.on_face_workplane = False

    # ------------------------------------------------------------------
    # profile ops (ported semantics)

    def _op_circle(self, step: TraceStep) -> None:
        pending: Dict[str, Any] = {
            "kind": "circle",
            "radius": float(step.args[0]),
            "plane": self.state.plane,
            "origin": self._profile_center(),
        }
        self.state.pending_profile = pending
        self.built_profile = True

    def _op_rect(self, step: TraceStep) -> None:
        self.state.pending_profile = {
            "kind": "rect",
            "width": float(step.args[0]),
            "height": float(step.args[1]),
            "plane": self.state.plane,
            "origin": self.state.origin,
        }
        self.built_profile = True

    def _op_polygon(self, step: TraceStep) -> None:
        n_sides = int(step.args[0])
        diameter = float(step.args[1])
        radius = diameter / 2.0
        points: List[Vec3] = []
        for index in range(n_sides):
            angle = 2.0 * math.pi * index / float(n_sides)
            points.append(self._global_point((radius * math.cos(angle), radius * math.sin(angle), 0.0)))
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
        self.built_profile = True

    def _op_polyline(self, step: TraceStep) -> None:
        raw_points = step.args[0]
        if self.state.pending_profile:
            kind = self.state.pending_profile.get("kind")
            if kind == "wire_path" and self.state.pending_profile.get("closed"):
                segments = self.state.pending_profile.get("segments", [])
                if segments and tuple(segments[0]["start"]) == tuple(segments[-1]["end"]):
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
        segments = []
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
        self.built_profile = True

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
        self.built_profile = True

    def _op_lineTo(self, step: TraceStep) -> None:
        end = self._global_point((float(step.args[0]), float(step.args[1]), 0.0))
        cursor = (
            self.state.pending_profile.get("cursor")
            if self.state.pending_profile
            else None
        )
        cursor_vec = _as_vec3(cursor) if cursor is not None else self.state.origin
        self._append_wire_segment(kind="line", start=cursor_vec, end=end)

    def _op_threePointArc(self, step: TraceStep) -> None:
        mid = self._global_point(
            (
                float(step.args[0][0]),
                float(step.args[0][1]),
                float(step.args[0][2]) if len(step.args[0]) >= 3 else 0.0,
            )
        )
        end = self._global_point(
            (
                float(step.args[1][0]),
                float(step.args[1][1]),
                float(step.args[1][2]) if len(step.args[1]) >= 3 else 0.0,
            )
        )
        cursor = (
            self.state.pending_profile.get("cursor")
            if self.state.pending_profile
            else None
        )
        cursor_vec = _as_vec3(cursor) if cursor is not None else self.state.origin
        self._append_wire_segment(kind="arc3", start=cursor_vec, mid=mid, end=end)

    def _op_close(self, step: TraceStep) -> None:
        del step
        if self.state.pending_profile and self.state.pending_profile.get("kind") == "wire_path":
            segments = self.state.pending_profile.get("segments", [])
            if segments:
                start = segments[0]["start"]
                end = segments[-1]["end"]
                if tuple(start) != tuple(end):
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

        def mirror_pt(point: Vec3) -> Vec3:
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

    def _op_slot2D(self, step: TraceStep) -> None:
        length_value = float(step.args[0])
        width_value = float(step.args[1])
        angle = float(step.args[2]) if len(step.args) > 2 else 0.0
        radius = width_value / 2.0
        half_straight = max((length_value - width_value) / 2.0, 0.0)

        def slot_point(u: float, v: float) -> Vec3:
            if abs(angle) > 1e-9:
                rad = math.radians(angle)
                cos_a = math.cos(rad)
                sin_a = math.sin(rad)
                u, v = u * cos_a - v * sin_a, u * sin_a + v * cos_a
            return self._global_point((u, v, 0.0))

        start = slot_point(-half_straight, radius)
        top_end = slot_point(half_straight, radius)
        right_mid = slot_point(half_straight + radius, 0.0)
        right_end = slot_point(half_straight, -radius)
        bottom_end = slot_point(-half_straight, -radius)
        left_mid = slot_point(-half_straight - radius, 0.0)
        segments = [
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
        }
        self.built_profile = True

    def _op_spline(self, step: TraceStep) -> None:
        raw_points = step.args[0] if step.args else []
        global_points: List[Vec3] = []
        for raw in raw_points:
            if isinstance(raw, (list, tuple)):
                local = (
                    float(raw[0]),
                    float(raw[1]),
                    float(raw[2]) if len(raw) >= 3 else 0.0,
                )
            else:
                local = _as_vec3(raw)
            global_points.append(self._global_point(local))
        self.state.pending_profile = {
            "kind": "spline_path",
            "plane": self.state.plane,
            "origin": self.state.origin,
            "points": global_points,
            "closed": False,
        }
        self.built_profile = True

    def _profile_center(self) -> Vec3:
        pending = self.state.pending_profile
        if pending and pending.get("kind") == "wire_path":
            cursor = pending.get("cursor")
            if isinstance(cursor, (list, tuple)) and len(cursor) >= 3:
                return (float(cursor[0]), float(cursor[1]), float(cursor[2]))
        return self.state.origin

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

    # ------------------------------------------------------------------
    # solid-producing ops

    def _op_box(self, step: TraceStep) -> None:
        width, height, depth = (float(v) for v in step.args[:3])
        var_base = self._open_block("box")
        var = self._tool_var(var_base)
        self.state.lines.append(
            f"    with scad.SimpleWorkplane("
            f"origin={fmt_vec(self.state.origin)}, normal={fmt_vec(self.state.normal)}, "
            f"x_dir={fmt_vec(self.state.u_dir)},):"
        )
        self.state.lines.append(
            f"        {var} = scad.make_box_rsolid("
            f"width={fmt_num(width)}, height={fmt_num(height)}, depth={fmt_num(depth)}, "
            f"bottom_face_center=(0, 0, -({fmt_num(depth)}) / 2.0),)"
        )
        if self._tool_mode:
            self.state.last_solid = var
        else:
            self._commit_add(var)
        self.state.pending_profile = None

    def _op_cylinder(self, step: TraceStep) -> None:
        height = float(step.args[0])
        radius = float(step.args[1])
        var_base = self._open_block("cylinder")
        var = self._tool_var(var_base)
        self.state.lines.append(
            f"    with scad.SimpleWorkplane("
            f"origin={fmt_vec(self.state.origin)}, normal={fmt_vec(self.state.normal)}, "
            f"x_dir={fmt_vec(self.state.u_dir)},):"
        )
        self.state.lines.append(
            f"        {var} = scad.make_cylinder_rsolid("
            f"radius={fmt_num(radius)}, height={fmt_num(height)}, "
            f"bottom_face_center=(0, 0, -({fmt_num(height)}) / 2.0), axis=(0, 0, 1),)"
        )
        if self._tool_mode:
            self.state.last_solid = var
        else:
            self._commit_add(var)
        self.state.pending_profile = None

    def _op_sphere(self, step: TraceStep) -> None:
        radius = float(step.args[0])
        var_base = self._open_block("sphere")
        var = self._tool_var(var_base)
        self.state.lines.append(
            f"    {var} = scad.make_sphere_rsolid("
            f"radius={fmt_num(radius)}, center={fmt_vec(self.state.origin)},)"
        )
        if self._tool_mode:
            self.state.last_solid = var
        else:
            self._commit_add(var)
        self.state.pending_profile = None

    def _op_extrude(self, step: TraceStep) -> None:
        if self.state.pending_profile is None:
            self.state.unsupported.append("extrude without pending profile")
            return
        distance = float(step.args[0])
        taper = step.kwargs.get("taper")
        profile = self._finalize_wire_profile()

        if taper is not None and profile.get("kind") != "circle":
            self.state.unsupported.append(f"extrude taper unsupported for profile kind {profile.get('kind')}")
            return

        if self.state.pending_rarray and not step.kwargs.get("both") and taper is None:
            self._emit_pattern_extrude(profile, distance)
            self.state.pending_profile = None
            self.state.pending_rarray = None
            return

        direction = self._extrude_direction()
        dist = abs(distance)
        if distance < 0:
            direction = (-direction[0], -direction[1], -direction[2])

        var_base = self._open_block("extrude", tiers=["profile=geometry"])
        var = self._tool_var(var_base)

        if taper is not None:
            self._emit_taper_extrude(var, profile, distance=dist, direction=direction, taper_deg=float(taper))
            if self._tool_mode:
                self.state.last_solid = var
            else:
                self._commit_add(var)
            self.state.pending_profile = None
            return

        if step.kwargs.get("both"):
            # CadQuery both=True extrudes `distance` in each direction:
            # shift the sketch plane down and extrude the full span.
            shifted = dict(profile)
            frame = dict(profile.get("frame", self._plane_frame()))
            origin = profile.get("origin", self.state.origin)
            shifted["origin"] = tuple(origin[i] - direction[i] * dist for i in range(3))
            shifted["frame"] = frame
            face_expr = self._emit_profile(var, shifted)
            self.state.lines.append(
                f"    {var} = scad.extrude_rsolid("
                f"profile={face_expr}, direction={fmt_vec(direction)}, "
                f"distance={fmt_num(dist * 2.0)},)"
            )
        else:
            frame = dict(profile.get("frame", self._plane_frame()))
            frame["extrude"] = direction
            profile = dict(profile)
            profile["frame"] = frame
            face_expr = self._emit_profile(var, profile)
            self.state.lines.append(
                f"    {var} = scad.extrude_rsolid("
                f"profile={face_expr}, direction={fmt_vec(direction)}, "
                f"distance={fmt_num(dist)},)"
            )
        if self._tool_mode:
            self.state.last_solid = var
        else:
            self._commit_add(var)
        self.state.pending_profile = None

    def _emit_taper_extrude(
        self,
        var: str,
        profile: Dict[str, Any],
        *,
        distance: float,
        direction: Vec3,
        taper_deg: float,
    ) -> None:
        """Taper extrusion of a circle = conical frustum: loft of two sketch
        circles (start radius, shrunk end radius shifted along the direction)."""
        origin = profile.get("origin", self.state.origin)
        frame = profile.get("frame", self._plane_frame())
        radius = float(profile["radius"])
        # CadQuery positive taper shrinks along the extrude direction.
        end_radius = radius - distance * math.tan(math.radians(taper_deg))
        if end_radius <= 1e-9:
            self.state.unsupported.append("extrude taper collapses the end radius")
            return
        end_center = tuple(origin[i] + direction[i] * distance for i in range(3))

        def emit_section(tag: str, center: Vec3, r: float) -> str:
            sketch = SketchScript(f"{var}_{tag}", center, frame.get("u", (1.0, 0.0, 0.0)), frame.get("v", (0.0, 1.0, 0.0)))
            center_ref = sketch.point(0.0, 0.0)
            sketch.circle(center_ref, r)
            self.state.lines.extend(sketch.render())
            self.state.lines.append(f"    {var}_{tag}_wire = scad.make_wire_from_sketch_rwire(s, profile=0)")
            return f"{var}_{tag}_wire"

        w0 = emit_section("p0", origin, radius)
        w1 = emit_section("p1", end_center, end_radius)
        self.state.lines.append(f"    {var} = scad.loft_rsolid(profiles=[{w0}, {w1}],)")

    def _op_revolve(self, step: TraceStep) -> None:
        if self.state.pending_profile is None:
            self.state.unsupported.append("revolve without pending profile")
            return
        profile = self._finalize_wire_profile()
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
        var_base = self._open_block("revolve", tiers=["profile=geometry"])
        var = self._tool_var(var_base)
        face_expr = self._emit_profile(var, profile)
        self.state.lines.append(
            f"    {var} = scad.revolve_rsolid("
            f"profile={face_expr}, axis={fmt_vec(axis)}, "
            f"angle={fmt_num(angle)}, origin={fmt_vec(axis_start)},)"
        )
        if self._tool_mode:
            self.state.last_solid = var
        else:
            self._commit_add(var)
        self.state.pending_profile = None

    def _op_loft(self, step: TraceStep) -> None:
        del step
        profiles = list(self.state.loft_profiles)
        if self.state.pending_profile:
            profiles.append(self._finalize_wire_profile())
        if len(profiles) < 2:
            self.state.unsupported.append("loft requires at least two profiles")
            return
        var_base = self._open_block("loft", tiers=["profile=geometry"])
        var = self._tool_var(var_base)
        wire_vars: List[str] = []
        for index, profile in enumerate(profiles):
            wire_expr = self._emit_profile(f"{var}_s{index}", profile, as_wire=True)
            wire_vars.append(wire_expr)
        profiles_arg = ", ".join(wire_vars)
        self.state.lines.append(f"    {var} = scad.loft_rsolid(profiles=[{profiles_arg}],)")
        if self._tool_mode:
            self.state.last_solid = var
        else:
            self._commit_add(var)
        self.state.loft_profiles = []
        self.state.pending_profile = None

    # ------------------------------------------------------------------
    # cuts

    def _emit_profile_cut(self, depth: float, *, op: str, thru: bool = False) -> None:
        if self.state.pending_profile is None:
            self.state.unsupported.append(f"{op} without pending profile")
            return
        if not self.state.bodies:
            self.state.unsupported.append(f"{op} without a base body")
            return
        profile = self._finalize_wire_profile()
        direction = self._cut_direction()
        cut_depth = self._thru_depth(direction) if thru else depth

        if self.state.pending_rarray:
            self._emit_pattern_cut(profile, cut_depth, op=op)
            self.state.pending_profile = None
            self.state.pending_rarray = None
            return

        var_base = self._open_block(op, tiers=["profile=geometry"])
        var = self._tool_var(var_base)
        frame = dict(profile.get("frame", self._plane_frame()))
        frame["extrude"] = direction
        profile = dict(profile)
        profile["frame"] = frame
        face_expr = self._emit_profile(var, profile)
        self.state.lines.append(
            f"    {var} = scad.extrude_rsolid("
            f"profile={face_expr}, direction={fmt_vec(direction)}, "
            f"distance={fmt_num(cut_depth)},)"
        )
        self._commit_cut([var])
        self.state.pending_profile = None

    def _op_cutBlind(self, step: TraceStep) -> None:
        self._emit_profile_cut(abs(float(step.args[0])), op="cutBlind")

    def _op_cutThruAll(self, step: TraceStep) -> None:
        del step
        self._emit_profile_cut(1000.0, op="cutThruAll", thru=True)

    def _pattern_loop_header(self, pattern: Dict[str, Any]) -> Tuple[List[str], str, str]:
        """Emit the loop scaffolding; returns (lines, indent, center expr)."""
        lines: List[str] = []
        if "points" in pattern:
            points = pattern["points"]
            lines.append("    for _c in [")
            for point in points:
                lines.append(f"        {fmt_vec(self._global_point((point[0], point[1], point[2] if len(point) > 2 else 0.0)))},")
            lines.append("    ]:")
            return lines, "        ", "_c"
        x_count = int(pattern["x_count"])
        y_count = int(pattern["y_count"])
        x_spacing = float(pattern["x_spacing"])
        y_spacing = float(pattern["y_spacing"])
        u_dir = self.state.u_dir
        v_dir = self.state.v_dir
        base_origin = self.state.origin
        lines.append(f"    for _ix in range({x_count}):")
        lines.append(f"        for _iy in range({y_count}):")
        lines.append(f"            _ox = (_ix - ({x_count} - 1) / 2.0) * {fmt_num(x_spacing)}")
        lines.append(f"            _oy = (_iy - ({y_count} - 1) / 2.0) * {fmt_num(y_spacing)}")
        center_expr = (
            f"({fmt_num(base_origin[0])} + _ox * {fmt_num(u_dir[0])} + _oy * {fmt_num(v_dir[0])}, "
            f"{fmt_num(base_origin[1])} + _ox * {fmt_num(u_dir[1])} + _oy * {fmt_num(v_dir[1])}, "
            f"{fmt_num(base_origin[2])} + _ox * {fmt_num(u_dir[2])} + _oy * {fmt_num(v_dir[2])})"
        )
        return lines, "            ", center_expr

    def _pattern_sketch_lines(self, profile: Dict[str, Any], var: str, center_expr: str, indent: str) -> List[str]:
        """Sketch + face lines inside a pattern loop; the plane origin is the
        loop variable expression, entity geometry is constant-local."""
        if profile["kind"] not in {"circle", "rect", "wire_path"}:
            raise ValueError(f"pattern profile kind {profile['kind']} not supported")
        probe = SketchScript(var, (0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        if profile["kind"] == "circle":
            center_ref = probe.point(0.0, 0.0)
            probe.circle(center_ref, float(profile["radius"]))
        elif profile["kind"] == "rect":
            hw = float(profile["width"]) / 2.0
            hh = float(profile["height"]) / 2.0
            refs = [probe.point(su * hw, sv * hh) for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
            refs.append(refs[0])
            for a, b in zip(refs, refs[1:]):
                probe.line(a, b)
        else:
            origin = profile["origin"]
            frame = profile.get("frame", self._plane_frame())
            for segment in profile["segments"]:
                if segment["kind"] == "line":
                    probe.line(
                        probe.point(*_global_to_local(origin, frame["u"], frame["v"], segment["start"])),
                        probe.point(*_global_to_local(origin, frame["u"], frame["v"], segment["end"])),
                    )
                elif segment["kind"] == "arc3":
                    probe.arc3(
                        _global_to_local(origin, frame["u"], frame["v"], segment["start"]),
                        _global_to_local(origin, frame["u"], frame["v"], segment["mid"]),
                        _global_to_local(origin, frame["u"], frame["v"], segment["end"]),
                    )
            if profile.get("closed"):
                pass  # polygon/polyline segments are already closed chains
        u_dir = profile.get("frame", self._plane_frame())["u"]
        v_dir = profile.get("frame", self._plane_frame())["v"]
        header = (
            f"{indent}s = scad.make_sketch_rsketch(name={var!r}, "
            f"plane={{'origin': {center_expr}, 'x_axis': {fmt_vec(u_dir)}, 'y_axis': {fmt_vec(v_dir)}}})"
        )
        return [header] + [indent + line for line in probe.lines[1:]]

    def _emit_pattern_cut(self, profile: Dict[str, Any], depth: float, *, op: str) -> None:
        pattern = self.state.pending_rarray or {}
        if "x_count" not in pattern and "points" not in pattern:
            self.state.unsupported.append("pattern cut without rarray or pushPoints")
            return
        direction = self._cut_direction()
        self._open_block("pattern_cut", tiers=["profile=geometry"])
        loop_lines, indent, center_expr = self._pattern_loop_header(pattern)
        self.state.lines.extend(loop_lines)
        try:
            sketch_lines = self._pattern_sketch_lines(profile, "pattern_cut", center_expr, indent)
        except ValueError as exc:
            self.state.unsupported.append(f"pattern cut: {exc}")
            self.state.lines.pop()  # drop the just-opened block header
            if self.features:
                self.features.pop()
            return
        self.state.lines.extend(sketch_lines)
        self.state.lines.append(
            f"{indent}_tool = scad.extrude_rsolid("
            f"profile=scad.make_face_from_sketch_rface(s, profile=0), "
            f"direction={fmt_vec(direction)}, distance={fmt_num(depth)},)"
        )
        self.state.lines.append(f"{indent}bodies = [scad.cut_rsolid(_b, [_tool]) for _b in bodies]")
        del op

    def _emit_pattern_extrude(self, profile: Dict[str, Any], distance: float) -> None:
        pattern = self.state.pending_rarray or {}
        if "x_count" not in pattern and "points" not in pattern:
            self.state.unsupported.append("pattern extrude without rarray or pushPoints")
            return
        if not self.state.bodies:
            self.state.unsupported.append("pattern extrude without base body")
            return
        direction = self._extrude_direction()
        self._open_block("pattern_extrude", tiers=["profile=geometry"])
        loop_lines, indent, center_expr = self._pattern_loop_header(pattern)
        self.state.lines.extend(loop_lines)
        try:
            sketch_lines = self._pattern_sketch_lines(profile, "pattern_boss", center_expr, indent)
        except ValueError as exc:
            self.state.unsupported.append(f"pattern extrude: {exc}")
            self.state.lines.pop()  # drop the just-opened block header
            if self.features:
                self.features.pop()
            return
        self.state.lines.extend(sketch_lines)
        self.state.lines.append(
            f"{indent}_tool = scad.extrude_rsolid("
            f"profile=scad.make_face_from_sketch_rface(s, profile=0), "
            f"direction={fmt_vec(direction)}, distance={fmt_num(abs(distance))},)"
        )
        self.state.lines.extend(
            [
                f"{indent}_merged = False",
                f"{indent}_next = []",
                f"{indent}for _b in bodies:",
                f"{indent}    try:",
                f"{indent}        _next.append(scad.union_rsolid(_b, [_tool]))",
                f"{indent}        _merged = True",
                f"{indent}    except Exception:",
                f"{indent}        _next.append(_b)",
                f"{indent}bodies = _next",
                f"{indent}if not _merged:",
                f"{indent}    bodies.extend([_tool])",
            ]
        )

    # ------------------------------------------------------------------
    # holes

    def _hole_centers(self) -> Tuple[List[Vec3], bool]:
        pattern = self.state.pending_rarray or {}
        centers: List[Vec3] = []
        if "points" in pattern:
            for point in pattern["points"]:
                centers.append(
                    self._global_point((float(point[0]), float(point[1]), float(point[2]) if len(point) > 2 else 0.0))
                )
            self.state.pending_rarray = None
            return centers, len(centers) > 1
        self.state.pending_rarray = None
        return [self.state.origin], False

    def _op_hole(self, step: TraceStep) -> None:
        if not self.state.bodies:
            self.state.unsupported.append("hole without a base body")
            return
        depth = step.kwargs.get("depth")
        if depth is None and len(step.args) >= 2:
            depth = step.args[1]
        radius = float(step.args[0]) / 2.0
        hole_dir = self._hole_direction()
        centers, is_pattern = self._hole_centers()
        hole_depth = float(depth) if depth is not None else self._thru_depth(hole_dir)

        self._open_block("hole", role="pattern" if is_pattern else None)
        tool_exprs: List[str] = []
        for index, center in enumerate(centers):
            var = f"hole_tool{index + 1}" if len(centers) > 1 else "hole_tool"
            if depth is not None:
                bottom = center
                height = hole_depth
            else:
                # Through hole: back off 1mm behind the entry face; the thru
                # depth already carries span + margin to clear the far side.
                bottom = tuple(center[i] - hole_dir[i] * 1.0 for i in range(3))
                height = hole_depth
            self.state.lines.append(
                f"    {var} = scad.make_cylinder_rsolid("
                f"radius={fmt_num(radius)}, height={fmt_num(height)}, "
                f"bottom_face_center={fmt_vec(bottom)}, axis={fmt_vec(hole_dir)},)"
            )
            tool_exprs.append(var)
        self._commit_cut(tool_exprs)

    def _op_cskHole(self, step: TraceStep) -> None:
        if not self.state.bodies:
            self.state.unsupported.append("cskHole without a base body")
            return
        if len(step.args) < 3:
            self.state.unsupported.append("cskHole requires diameter, cskDiameter, cskAngle")
            return
        diameter, csk_diameter, csk_angle = (float(v) for v in step.args[:3])
        depth = step.kwargs.get("depth")
        hole_r = diameter / 2.0
        csk_r = csk_diameter / 2.0
        normal = self.state.normal
        hole_dir = self._hole_direction()
        centers, is_pattern = self._hole_centers()
        hole_depth = float(depth) if depth is not None else self._thru_depth(hole_dir)
        # Depth of the countersink cone: (R_csk - R_hole) / tan(half angle).
        csk_depth = (csk_r - hole_r) / math.tan(math.radians(csk_angle / 2.0))

        self._open_block("cskHole", role="pattern" if is_pattern else None)
        u_dir, v_dir = self.state.u_dir, self.state.v_dir
        tool_exprs: List[str] = []
        for index, center in enumerate(centers):
            tag = f"csk{index + 1}" if len(centers) > 1 else "csk"
            bore = f"{tag}_bore"
            if depth is not None:
                bottom = center
                height = hole_depth
            else:
                bottom = tuple(center[i] - hole_dir[i] * 1.0 for i in range(3))
                height = hole_depth
            self.state.lines.append(
                f"    {bore} = scad.make_cylinder_rsolid("
                f"radius={fmt_num(hole_r)}, height={fmt_num(height)}, "
                f"bottom_face_center={fmt_vec(bottom)}, axis={fmt_vec(hole_dir)},)"
            )
            tool_exprs.append(bore)

            # Countersink cone: loft of two sketch circles (surface -> cone tip depth).
            end_center = (
                center[0] + hole_dir[0] * csk_depth,
                center[1] + hole_dir[1] * csk_depth,
                center[2] + hole_dir[2] * csk_depth,
            )
            cone = f"{tag}_cone"
            w0 = self._circle_sketch_wire(f"{tag}_c0", center, csk_r, u_dir, v_dir)
            w1 = self._circle_sketch_wire(f"{tag}_c1", end_center, hole_r, u_dir, v_dir)
            self.state.lines.append(f"    {cone} = scad.loft_rsolid(profiles=[{w0}, {w1}],)")
            tool_exprs.append(cone)
        self._commit_cut(tool_exprs)
        del normal

    def _circle_sketch_wire(self, name: str, center: Vec3, radius: float, u_dir: Vec3, v_dir: Vec3) -> str:
        sketch = SketchScript(name, center, u_dir, v_dir)
        center_ref = sketch.point(0.0, 0.0)
        sketch.circle(center_ref, radius)
        self.state.lines.extend(sketch.render())
        self.state.lines.append(f"    {name}_wire = scad.make_wire_from_sketch_rwire(s, profile=0)")
        return f"{name}_wire"

    # ------------------------------------------------------------------
    # bare booleans (no tool workplane)

    def _op_cut(self, step: TraceStep) -> None:
        if step.args and _is_workplane_ref(step.args[0]):
            return
        tool = self.state.last_solid
        if tool is None or tool in self.state.bodies:
            self.state.unsupported.append("cut without distinct tool solid")
            return
        self._open_block("cut")
        self._commit_cut([tool])

    def _op_union(self, step: TraceStep) -> None:
        if step.args and _is_workplane_ref(step.args[0]):
            return
        tool = self.state.last_solid
        if tool is None or tool in self.state.bodies:
            self.state.unsupported.append("union without distinct tool solid")
            return
        self._open_block("union")
        self._commit_add(tool)

    def _op_intersect(self, step: TraceStep) -> None:
        if step.args and _is_workplane_ref(step.args[0]):
            return
        tool = self.state.last_solid
        if tool is None or tool in self.state.bodies:
            self.state.unsupported.append("intersect without distinct tool solid")
            return
        self._open_block("intersect")
        self._commit_intersect(tool)

    # ------------------------------------------------------------------
    # modifiers

    def _edge_selection(self, step: TraceStep) -> Optional[str]:
        fingerprints = list(step.selections) or list(self.state.pending_edge_selections)
        chain = emit_ql_edges_selector(fingerprints)
        if chain is None:
            return None
        self.state.uses_ql = True
        return chain

    def _op_fillet(self, step: TraceStep) -> None:
        if not self.state.bodies:
            self.state.unsupported.append("fillet without a base body")
            return
        radius = float(step.args[0])
        edges = self._edge_selection(step)
        if edges is None:
            self.state.unsupported.append(
                f"fillet: no translatable edge selection (selector={self.state.pending_edge_selector!r})"
            )
            self.state.pending_edge_selector = None
            self.state.pending_edge_selections = []
            return
        self._open_block("fillet")
        self._commit_modify(f"scad.fillet_rsolid(solid=_b, edges={edges}, radius={fmt_num(radius)})")
        self.state.pending_edge_selector = None
        self.state.pending_edge_selections = []
        self.state.pending_face_selector = None
        self.state.pending_face_selections = []

    def _op_chamfer(self, step: TraceStep) -> None:
        if not self.state.bodies:
            self.state.unsupported.append("chamfer without a base body")
            return
        distance = float(step.args[0])
        edges = self._edge_selection(step)
        if edges is None:
            self.state.unsupported.append(
                f"chamfer: no translatable edge selection (selector={self.state.pending_edge_selector!r})"
            )
            self.state.pending_edge_selector = None
            self.state.pending_edge_selections = []
            return
        self._open_block("chamfer")
        self._commit_modify(f"scad.chamfer_rsolid(solid=_b, edges={edges}, distance={fmt_num(distance)})")
        self.state.pending_edge_selector = None
        self.state.pending_edge_selections = []
        self.state.pending_face_selector = None
        self.state.pending_face_selections = []

    def _op_shell(self, step: TraceStep) -> None:
        if not self.state.bodies:
            self.state.unsupported.append("shell without a base body")
            return
        thickness = abs(float(step.args[0]))
        fingerprints = list(self.state.pending_face_selections)
        faces = emit_ql_faces_selector(fingerprints, fallback_selector=self.state.pending_face_selector)
        if faces is None:
            self.state.unsupported.append(
                f"shell: no translatable face selection (selector={self.state.pending_face_selector!r})"
            )
            self.state.pending_face_selector = None
            self.state.pending_face_selections = []
            return
        self.state.uses_ql = True
        self._open_block("shell")
        self._commit_modify(f"scad.shell_rsolid(solid=_b, faces_to_remove={faces}, thickness={fmt_num(thickness)})")
        self.state.pending_face_selector = None
        self.state.pending_face_selections = []


# Imported late to avoid a cycle in the type checker's first pass.


def replay_trace_to_ftc(trace: OperationTrace, *, stem: str) -> Tuple[str, Dict[str, Any]]:
    """Library entry: CadQuery trace → FTC source + translation meta."""
    replayer = TraceReplayer(stem, cq_bbox=trace.cq_bbox)
    return replayer.replay(trace)
