"""Lower CadQuery method chains to feature IR."""

from __future__ import annotations

import ast
import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .ir import (
    FeatureProgram,
    FeatureStep,
    add_vec,
    local_to_global,
    plane_vectors,
    point_on_plane,
    regular_polygon_points,
)


@dataclass
class ChainOp:
    name: str
    args: Tuple[Any, ...]
    kwargs: Dict[str, Any]
    raw_args: Tuple[ast.AST, ...] = ()


@dataclass
class WorkplaneState:
    plane: str = "XY"
    origin: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    pending_profile: Optional[Dict[str, Any]] = None
    loft_profiles: List[Dict[str, Any]] = field(default_factory=list)
    body: Optional[str] = None
    pending_selector: Optional[Tuple[str, str]] = None
    pending_rarray: Optional[Dict[str, Any]] = None


class CadQueryParseError(ValueError):
    pass


def _literal(node: ast.AST) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        value = _literal(node.operand)
        if isinstance(value, (int, float)):
            return -value
    if isinstance(node, ast.Tuple):
        return tuple(_literal(elt) for elt in node.elts)
    if isinstance(node, ast.List):
        return [_literal(elt) for elt in node.elts]
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name) and node.func.value.id == "cq":
            if node.func.attr == "Vector" and len(node.args) >= 3:
                return (
                    float(_literal(node.args[0])),
                    float(_literal(node.args[1])),
                    float(_literal(node.args[2])),
                )
    raise CadQueryParseError(f"unsupported literal node: {ast.dump(node)}")


def _call_args(node: ast.Call) -> Tuple[Tuple[Any, ...], Dict[str, Any], Tuple[ast.AST, ...]]:
    parsed_args: List[Any] = []
    for arg in node.args:
        try:
            parsed_args.append(_literal(arg))
        except CadQueryParseError:
            parsed_args.append(arg)
    kwargs: Dict[str, Any] = {}
    for kw in node.keywords:
        if not kw.arg:
            continue
        try:
            kwargs[kw.arg] = _literal(kw.value)
        except CadQueryParseError:
            kwargs[kw.arg] = kw.value
    return tuple(parsed_args), kwargs, tuple(node.args)


def unwrap_chain(node: ast.AST) -> Tuple[List[ChainOp], ast.AST]:
    ops: List[ChainOp] = []
    current = node
    while isinstance(current, ast.Call):
        func = current.func
        if not isinstance(func, ast.Attribute):
            break
        args, kwargs, raw_args = _call_args(current)
        ops.append(ChainOp(name=func.attr, args=args, kwargs=kwargs, raw_args=raw_args))
        current = func.value
    ops.reverse()
    return ops, current


def _as_vec3(value: Any) -> Tuple[float, float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 3:
        return (float(value[0]), float(value[1]), float(value[2]))
    raise CadQueryParseError(f"expected 3-vector, got {value!r}")


def _as_xy(value: Any) -> Tuple[float, float]:
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return (float(value[0]), float(value[1]))
    raise CadQueryParseError(f"expected 2D point, got {value!r}")


class ChainLowerer:
    def __init__(self, program: FeatureProgram) -> None:
        self.program = program
        self._feature_no = 0

    def _next_step(self, kind: str, description: str, params: Dict[str, Any]) -> FeatureStep:
        self._feature_no += 1
        return FeatureStep(index=self._feature_no, kind=kind, description=description, params=params)

    def _note_unsupported(self, message: str) -> None:
        if message not in self.program.unsupported:
            self.program.unsupported.append(message)

    def _note_warning(self, message: str) -> None:
        if message not in self.program.warnings:
            self.program.warnings.append(message)

    def _apply_transformed(self, state: WorkplaneState, op: ChainOp) -> None:
        offset = op.kwargs.get("offset", (0.0, 0.0, 0.0))
        rotate = op.kwargs.get("rotate", (0.0, 0.0, 0.0))
        if isinstance(offset, (list, tuple)):
            local = _as_vec3(offset)
            state.origin = local_to_global(state.plane, state.origin, local)
        if isinstance(rotate, (list, tuple)):
            rx, ry, rz = _as_vec3(rotate)
            if any(abs(v) > 1e-9 for v in (rx, ry, rz)):
                self._note_warning(
                    f"transformed rotate=({rx}, {ry}, {rz}) not applied; using translation only"
                )

    def _finalize_wire_profile(self, state: WorkplaneState) -> Dict[str, Any]:
        profile = state.pending_profile
        if profile is None:
            raise CadQueryParseError("missing pending profile")
        if profile.get("kind") != "wire_path":
            return profile
        segments = profile["segments"]
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
        return {
            "kind": "wire_path",
            "plane": state.plane,
            "origin": state.origin,
            "segments": segments,
            "points": points,
            "closed": profile.get("closed", False),
        }

    def _set_circle_profile(self, state: WorkplaneState, radius: float) -> None:
        state.pending_profile = {
            "kind": "circle",
            "radius": float(radius),
            "plane": state.plane,
            "origin": state.origin,
        }

    def _stash_profile_for_loft(self, state: WorkplaneState) -> None:
        if state.pending_profile is None:
            return
        state.loft_profiles.append(self._finalize_wire_profile(state))
        state.pending_profile = None

    def _append_wire_segment(
        self,
        state: WorkplaneState,
        *,
        kind: str,
        start: Tuple[float, float, float],
        end: Tuple[float, float, float],
        mid: Optional[Tuple[float, float, float]] = None,
    ) -> None:
        if state.pending_profile is None or state.pending_profile.get("kind") != "wire_path":
            state.pending_profile = {
                "kind": "wire_path",
                "plane": state.plane,
                "origin": state.origin,
                "segments": [],
                "closed": False,
                "cursor": start,
            }
        segment: Dict[str, Any] = {"kind": kind, "start": start, "end": end}
        if mid is not None:
            segment["mid"] = mid
        state.pending_profile["segments"].append(segment)
        state.pending_profile["cursor"] = end

    def lower_ops(
        self,
        ops: Sequence[ChainOp],
        *,
        initial_plane: str,
        result_prefix: str,
        initial_body: Optional[str] = None,
    ) -> Optional[str]:
        state = WorkplaneState(plane=initial_plane.upper(), body=initial_body)
        result_var = initial_body or "body"

        index = 0
        while index < len(ops):
            op = ops[index]
            index += 1

            if op.name == "Workplane":
                if op.args:
                    state.plane = str(op.args[0]).upper()
                continue

            if op.name == "transformed":
                self._apply_transformed(state, op)
                continue

            if op.name == "workplane":
                self._stash_profile_for_loft(state)
                state.pending_selector = None
                if "offset" in op.kwargs:
                    offset = float(op.kwargs["offset"])
                    normal = plane_vectors(state.plane)["normal"]
                    state.origin = add_vec(state.origin, scale(normal, offset))
                continue

            if op.name == "faces" and op.args:
                state.pending_selector = ("faces", str(op.args[0]))
                continue

            if op.name == "edges" and op.args:
                state.pending_selector = ("edges", str(op.args[0]))
                continue

            if op.name == "center" and op.args:
                xy = _as_xy(op.args[0])
                state.origin = point_on_plane(state.plane, state.origin, xy, 0.0)
                continue

            if op.name == "rarray" and len(op.args) >= 4:
                state.pending_rarray = {
                    "x_spacing": float(op.args[0]),
                    "y_spacing": float(op.args[1]),
                    "x_count": int(op.args[2]),
                    "y_count": int(op.args[3]),
                }
                continue

            if op.name == "polarArray" and len(op.args) >= 2:
                state.pending_rarray = {
                    "polar": True,
                    "radius": float(op.args[0]),
                    "count": int(op.args[1]),
                    "start_angle": float(op.args[2]) if len(op.args) >= 3 else 0.0,
                }
                continue

            if op.name == "pushPoints" and op.args:
                state.pending_rarray = {"points": op.args[0]}
                continue

            if op.name == "box" and len(op.args) >= 3:
                step = self._next_step(
                    "box_solid",
                    "box",
                    {
                        "plane": state.plane,
                        "width": float(op.args[0]),
                        "height": float(op.args[1]),
                        "depth": float(op.args[2]),
                        "origin": state.origin,
                        "result_var": state.body or "body",
                    },
                )
                self.program.steps.append(step)
                result_var = step.params["result_var"]
                state.body = result_var
                state.pending_profile = None
                continue

            if op.name == "cylinder" and len(op.args) >= 2:
                step = self._next_step(
                    "cylinder_solid",
                    "cylinder",
                    {
                        "plane": state.plane,
                        "height": float(op.args[0]),
                        "radius": float(op.args[1]),
                        "origin": state.origin,
                        "result_var": state.body or "body",
                    },
                )
                self.program.steps.append(step)
                result_var = step.params["result_var"]
                state.body = result_var
                continue

            if op.name == "sphere" and op.args:
                step = self._next_step(
                    "sphere_solid",
                    "sphere",
                    {
                        "radius": float(op.args[0]),
                        "origin": state.origin,
                        "result_var": state.body or "body",
                    },
                )
                self.program.steps.append(step)
                result_var = step.params["result_var"]
                state.body = result_var
                continue

            if op.name == "circle" and op.args:
                self._set_circle_profile(state, float(op.args[0]))
                continue

            if op.name == "rect" and len(op.args) >= 2:
                state.pending_profile = {
                    "kind": "rect",
                    "width": float(op.args[0]),
                    "height": float(op.args[1]),
                    "plane": state.plane,
                    "origin": state.origin,
                }
                continue

            if op.name == "polygon" and len(op.args) >= 2:
                n_sides = int(op.args[0])
                diameter = float(op.args[1])
                state.pending_profile = {
                    "kind": "polygon",
                    "n_sides": n_sides,
                    "diameter": diameter,
                    "points": regular_polygon_points(n_sides, diameter, state.plane, state.origin),
                }
                continue

            if op.name == "polyline" and op.args:
                raw_points = op.args[0]
                points = [
                    point_on_plane(state.plane, state.origin, _as_xy(item), 0.0)
                    for item in raw_points
                ]
                state.pending_profile = {
                    "kind": "polyline",
                    "points": points,
                    "plane": state.plane,
                    "origin": state.origin,
                }
                continue

            if op.name == "moveTo" and len(op.args) >= 2:
                start = point_on_plane(state.plane, state.origin, (float(op.args[0]), float(op.args[1])), 0.0)
                state.pending_profile = {
                    "kind": "wire_path",
                    "plane": state.plane,
                    "origin": state.origin,
                    "segments": [],
                    "closed": False,
                    "cursor": start,
                }
                continue

            if op.name == "lineTo" and len(op.args) >= 2:
                end = point_on_plane(state.plane, state.origin, (float(op.args[0]), float(op.args[1])), 0.0)
                cursor = state.pending_profile.get("cursor") if state.pending_profile else None
                if cursor is None:
                    cursor = state.origin
                self._append_wire_segment(state, kind="line", start=cursor, end=end)
                continue

            if op.name == "threePointArc" and len(op.args) >= 2:
                mid = point_on_plane(state.plane, state.origin, _as_xy(op.args[0]), 0.0)
                end = point_on_plane(state.plane, state.origin, _as_xy(op.args[1]), 0.0)
                cursor = state.pending_profile.get("cursor") if state.pending_profile else state.origin
                self._append_wire_segment(state, kind="arc3", start=cursor, mid=mid, end=end)
                continue

            if op.name == "close":
                if state.pending_profile and state.pending_profile.get("kind") == "wire_path":
                    state.pending_profile["closed"] = True
                continue

            if op.name == "extrude" and op.args:
                result_var = state.body or "body"
                step = self._next_step(
                    "extrude_profile",
                    "extrude",
                    {
                        "plane": state.plane,
                        "distance": float(op.args[0]),
                        "both": bool(op.kwargs.get("both", False)),
                        "profile": self._finalize_wire_profile(state),
                        "origin": state.origin,
                        "result_var": result_var,
                    },
                )
                self.program.steps.append(step)
                state.body = result_var
                state.pending_profile = None
                continue

            if op.name == "cutBlind" and op.args:
                if state.pending_profile is None:
                    self._note_unsupported("cutBlind without pending profile")
                    continue
                depth = abs(float(op.args[0]))
                profile = self._finalize_wire_profile(state)
                if state.pending_rarray:
                    step = self._next_step(
                        "pattern_cut",
                        "pattern pocket cut",
                        {
                            "plane": state.plane,
                            "depth": depth,
                            "profile": profile,
                            "pattern": dict(state.pending_rarray),
                            "selector": state.pending_selector,
                            "target_var": state.body or result_var,
                            "result_var": state.body or result_var,
                        },
                    )
                    state.pending_rarray = None
                else:
                    step = self._next_step(
                        "blind_cut",
                        "blind cut",
                        {
                            "plane": state.plane,
                            "depth": depth,
                            "profile": profile,
                            "selector": state.pending_selector,
                            "target_var": state.body or result_var,
                            "result_var": state.body or result_var,
                        },
                    )
                self.program.steps.append(step)
                state.pending_profile = None
                state.pending_selector = None
                continue

            if op.name == "revolve" and op.args:
                profile = self._finalize_wire_profile(state)
                axis_start = _as_vec3(op.args[1]) if len(op.args) >= 2 else (0.0, 0.0, 0.0)
                axis_end = _as_vec3(op.args[2]) if len(op.args) >= 3 else (0.0, 0.0, 1.0)
                axis = (
                    axis_end[0] - axis_start[0],
                    axis_end[1] - axis_start[1],
                    axis_end[2] - axis_start[2],
                )
                step = self._next_step(
                    "revolve_profile",
                    "revolve",
                    {
                        "angle": float(op.args[0]),
                        "axis": axis,
                        "origin": axis_start,
                        "profile": profile,
                        "result_var": result_prefix if not state.body else f"{result_prefix}_rev",
                    },
                )
                self.program.steps.append(step)
                result_var = step.params["result_var"]
                state.body = result_var
                state.pending_profile = None
                continue

            if op.name == "loft":
                profiles = list(state.loft_profiles)
                if state.pending_profile:
                    profiles.append(self._finalize_wire_profile(state))
                if len(profiles) < 2:
                    self._note_unsupported("loft requires at least two profiles")
                    continue
                step = self._next_step(
                    "loft",
                    "loft",
                    {
                        "profiles": profiles,
                        "result_var": result_prefix if not state.body else f"{result_prefix}_loft",
                    },
                )
                self.program.steps.append(step)
                result_var = step.params["result_var"]
                state.body = result_var
                state.loft_profiles = []
                state.pending_profile = None
                continue

            if op.name == "hole" and op.args:
                step = self._next_step(
                    "through_hole",
                    "through hole",
                    {
                        "plane": state.plane,
                        "diameter": float(op.args[0]),
                        "origin": state.origin,
                        "selector": state.pending_selector,
                        "target_var": state.body or result_var,
                        "result_var": state.body or result_var,
                    },
                )
                self.program.steps.append(step)
                state.pending_selector = None
                continue

            if op.name == "cutThruAll":
                if state.pending_profile is None:
                    self._note_unsupported("cutThruAll without pending profile")
                    continue
                step = self._next_step(
                    "through_cut_profile",
                    "through cut",
                    {
                        "plane": state.plane,
                        "profile": self._finalize_wire_profile(state),
                        "origin": state.origin,
                        "selector": state.pending_selector,
                        "target_var": state.body or result_var,
                        "result_var": state.body or result_var,
                    },
                )
                self.program.steps.append(step)
                state.pending_profile = None
                state.pending_selector = None
                continue

            if op.name in {"cut", "union", "intersect"} and op.raw_args:
                nested_ops, _root = unwrap_chain(op.raw_args[0])
                if not nested_ops or nested_ops[0].name != "Workplane":
                    self._note_unsupported(f"{op.name} argument is not a Workplane chain")
                    continue
                nested_plane = str(nested_ops[0].args[0]).upper() if nested_ops[0].args else "XY"
                tool_prefix = f"tool_{self._feature_no + 1}"
                tool_var = self.lower_ops(nested_ops[1:], initial_plane=nested_plane, result_prefix=tool_prefix)
                if tool_var is None:
                    self._note_unsupported(f"{op.name}(...) nested tool not lowered")
                    continue
                mode = {"cut": "cut", "union": "union", "intersect": "intersect"}[op.name]
                step = self._next_step(
                    "boolean",
                    f"{mode} tool",
                    {
                        "mode": mode,
                        "target_var": state.body or result_var,
                        "tool_var": tool_var,
                        "result_var": state.body or result_var,
                    },
                )
                self.program.steps.append(step)
                result_var = step.params["result_var"]
                state.body = result_var
                continue

            if op.name == "chamfer" and op.args:
                step = self._next_step(
                    "chamfer",
                    "edge chamfer",
                    {
                        "distance": float(op.args[0]),
                        "selector": state.pending_selector,
                        "target_var": state.body or result_var,
                        "result_var": state.body or result_var,
                    },
                )
                self.program.steps.append(step)
                state.pending_selector = None
                continue

            if op.name == "fillet" and op.args:
                step = self._next_step(
                    "fillet",
                    "edge fillet",
                    {
                        "radius": float(op.args[0]),
                        "selector": state.pending_selector,
                        "target_var": state.body or result_var,
                        "result_var": state.body or result_var,
                    },
                )
                self.program.steps.append(step)
                state.pending_selector = None
                continue

            if op.name == "shell" and op.args:
                self._note_unsupported("shell not lowered yet")
                continue

            if op.name == "sweep":
                self._note_unsupported("sweep not lowered yet")
                continue

            if op.name in {"radiusArc", "slot2D", "ellipse", "mirrorY", "mirrorX", "makeHelix"}:
                self._note_unsupported(f"op {op.name} not lowered yet")
                continue

            self._note_unsupported(f"unsupported op: {op.name}")

        return state.body or result_var


def scale(normal: Tuple[float, float, float], value: float) -> Tuple[float, float, float]:
    return (normal[0] * value, normal[1] * value, normal[2] * value)
