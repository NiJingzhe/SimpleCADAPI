#!/usr/bin/env python3
"""Translate HistCAD sequence JSON into SimpleCADAPI FTC feature-tree sources.

The translator emits one feature block per HistCAD step (sketch entities ->
promotion -> extrude -> boolean mode), following the Feature Tree Convention:
block headers ``# ---- feature: <slug> (<role>) ----``, explicit dataflow
rebinding, and honest tier annotations (``profile=geometry`` for transcribed
dataset geometry; ``profile=sketch`` only when every HistCAD constraint maps
onto a native sketch constraint).

Usage:
    python tools/research/histcad_to_ftc.py <seq.json> [--out PATH]
        [--constraints auto|off|on]
    python tools/research/histcad_to_ftc.py --tar A.tar.gz --step-tar B.tar.gz
        [--execute K] [--stride N] [--workers W] [--out-dir DIR]

``--execute`` rebuilds a strided sample of models and reconciles total volume
against the packaged STEP ground truth.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
import tarfile
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

_POINT_TOL = 6

# ---------------------------------------------------------------------------
# value expressions

_UNIT_TO_MM = {
    "mm": 1.0, "millimeter": 1.0, "millimetre": 1.0,
    "cm": 10.0, "centimeter": 10.0, "centimetre": 10.0,
    "m": 1000.0, "meter": 1000.0, "meters": 1000.0,
    "in": 25.4, "inch": 25.4, "inches": 25.4,
    "ft": 304.8, "foot": 304.8, "feet": 304.8,
    "yd": 914.4, "yard": 914.4, "yards": 914.4,
}

_EXPR_TOKEN = re.compile(r"[A-Za-z]+|[0-9]*\.?[0-9]+|[()+\-*/]")


def eval_value_expr(value: Any) -> Optional[float]:
    """Evaluate a HistCAD value_expr into millimeters (None when unmappable)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str):
        return None
    tokens: List[str] = []
    for token in _EXPR_TOKEN.findall(value.strip()):
        if token in "+-*/()":
            tokens.append(token)
        elif re.fullmatch(r"[0-9]*\.?[0-9]+", token):
            tokens.append(token)
        else:
            factor = _UNIT_TO_MM.get(token.lower().rstrip("s") if token.lower().endswith("s") and token.lower()[:-1] in _UNIT_TO_MM else token.lower())
            if factor is None:
                factor = _UNIT_TO_MM.get(token.lower())
            if factor is None:
                return None
            tokens.append(repr(factor))
    if not tokens:
        return None
    # Insert explicit multiplication between adjacent numeric tokens so
    # "78 mm" becomes "78*1.0" and "(20/12) ft" becomes "( 20 / 12 )*304.8".
    joined: List[str] = []
    for token in tokens:
        if (
            joined
            and joined[-1] not in "+-*/("
            and token not in "+-*/)"
        ):
            joined.append("*")
        joined.append(token)
    try:
        result = eval(" ".join(joined), {"__builtins__": {}}, {})  # noqa: S307
    except Exception:
        return None
    return float(result) if isinstance(result, (int, float)) and math.isfinite(result) else None


# ---------------------------------------------------------------------------
# geometry helpers


def euler_to_axes(euler: Sequence[float]) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]:
    """Rotation basis from HistCAD Euler angles [alpha, beta, gamma] (degrees).

    Convention: R = Rx(alpha) @ Ry(beta) @ Rz(gamma) — calibrated against the
    packaged STEP ground truth (mixed-angle samples match exactly, while the
    reversed composition leaves several percent of volume unexplained).
    """
    alpha, beta, gamma = (math.radians(float(v)) for v in euler)

    def rotate(v: Tuple[float, float, float]) -> Tuple[float, float, float]:
        x, y, z = v
        x, y, z = (x * math.cos(gamma) - y * math.sin(gamma), x * math.sin(gamma) + y * math.cos(gamma), z)
        x, y, z = (x * math.cos(beta) + z * math.sin(beta), y, -x * math.sin(beta) + z * math.cos(beta))
        return (
            x,
            y * math.cos(alpha) - z * math.sin(alpha),
            y * math.sin(alpha) + z * math.cos(alpha),
        )

    return rotate((1.0, 0.0, 0.0)), rotate((0.0, 1.0, 0.0))


def cross(a: Sequence[float], b: Sequence[float]) -> Tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def circumcenter(p0, pm, p1) -> Tuple[float, float]:
    d = 2.0 * (p0[0] * (pm[1] - p1[1]) + pm[0] * (p1[1] - p0[1]) + p1[0] * (p0[1] - pm[1]))
    if abs(d) < 1e-12:
        raise ValueError("collinear arc points")
    ux = ((p0[0] ** 2 + p0[1] ** 2) * (pm[1] - p1[1]) + (pm[0] ** 2 + pm[1] ** 2) * (p1[1] - p0[1]) + (p1[0] ** 2 + p1[1] ** 2) * (p0[1] - pm[1])) / d
    uy = ((p0[0] ** 2 + p0[1] ** 2) * (p1[0] - pm[0]) + (pm[0] ** 2 + pm[1] ** 2) * (p0[0] - p1[0]) + (p1[0] ** 2 + p1[1] ** 2) * (pm[0] - p0[0])) / d
    return ux, uy


def knot_multiplicities(flat: Sequence[float]) -> Tuple[List[float], List[int]]:
    knots: List[float] = []
    mults: List[int] = []
    for knot in flat:
        if knots and abs(float(knot) - knots[-1]) < 1e-12:
            mults[-1] += 1
        else:
            knots.append(float(knot))
            mults.append(1)
    return knots, mults


def _fmt(value: float) -> str:
    return repr(round(float(value), 9))


def _vec(values: Sequence[float]) -> str:
    return "(" + ", ".join(_fmt(v) for v in values) + ")"


def _pt_key(point: Sequence[float]) -> Tuple[float, float]:
    return (round(float(point[0]), _POINT_TOL), round(float(point[1]), _POINT_TOL))


_KIND_PREFIXES = ("elliptical_arc", "ellipse", "circle", "nurbs", "arc", "line", "point")


def entity_kind(entity_id: str) -> str:
    for prefix in _KIND_PREFIXES:
        if entity_id.startswith(prefix + "_") or entity_id == prefix:
            return prefix
    return "unknown"


# ---------------------------------------------------------------------------
# sketch structure analysis (mirrors Sketch profile ordering)


def _sample_entity(kind: str, data: Dict[str, Any], count: int = 12) -> List[Tuple[float, float]]:
    if kind == "circle":
        cx, cy = data["center"]
        r = float(data["radius"])
        return [(cx + r * math.cos(2 * math.pi * i / count), cy + r * math.sin(2 * math.pi * i / count)) for i in range(count)]
    if kind == "ellipse":
        cx, cy = data["center"]
        a, b = float(data["major"]), float(data["minor"])
        theta = math.radians(float(data.get("angle", 0.0)))
        pts = []
        for i in range(count):
            phi = 2 * math.pi * i / count
            px, py = a * math.cos(phi), b * math.sin(phi)
            pts.append((cx + px * math.cos(theta) - py * math.sin(theta), cy + px * math.sin(theta) + py * math.cos(theta)))
        return pts
    if kind == "arc":
        p0, pm, p1 = data["start"], data["middle"], data["end"]
        cx, cy = circumcenter(p0, pm, p1)
        r = math.dist((cx, cy), p0)
        a0 = math.atan2(p0[1] - cy, p0[0] - cx)
        a1 = math.atan2(p1[1] - cy, p1[0] - cx)
        sweep = (a1 - a0) % (2 * math.pi)
        return [(cx + r * math.cos(a0 + sweep * i / (count - 1)), cy + r * math.sin(a0 + sweep * i / (count - 1))) for i in range(count)]
    if kind == "line":
        return [tuple(data["start"]), tuple(data["end"])]
    if kind == "nurbs":
        controls = data.get("controls") or []
        if len(controls) >= 2 and not data.get("periodic"):
            pts = [tuple(c) for c in controls]
            step = max(1, (len(pts) - 1) // 12)
            return pts[::step] + [pts[-1]]
    return []


def _edge_endpoints(kind: str, data: Dict[str, Any]) -> List[Tuple[float, float]]:
    if kind == "line":
        return [tuple(data["start"]), tuple(data["end"])]
    if kind == "arc":
        return [tuple(data["start"]), tuple(data["end"])]
    if kind == "nurbs":
        controls = data.get("controls") or []
        if len(controls) >= 2 and not data.get("periodic"):
            return [tuple(controls[0]), tuple(controls[-1])]
        return []
    return []


def classify_profiles(sketch: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Ordered profile descriptors matching Sketch._profiles_from_solution.

    Circles and ellipses become standalone profiles in entity order; chains of
    line/arc/nurbs entities become edge components keyed by shared pooled
    endpoints. Each descriptor carries samples for containment nesting.
    """
    profiles: List[Dict[str, Any]] = []
    edge_ids: List[str] = []
    endpoints_by_entity: Dict[str, List[Tuple[float, float]]] = {}
    for eid, data in sketch.items():
        if not isinstance(data, dict):
            continue
        kind = entity_kind(eid)
        if kind in {"circle", "ellipse"}:
            profiles.append({"index": len(profiles), "kind": kind, "entity_ids": [eid], "samples": _sample_entity(kind, data)})
        elif kind in {"line", "arc", "nurbs"}:
            edge_ids.append(eid)
            endpoints_by_entity[eid] = [_pt_key(p) for p in _edge_endpoints(kind, data)]

    edges_at_point: Dict[Tuple[float, float], List[str]] = defaultdict(list)
    for eid, endpoints in endpoints_by_entity.items():
        for key in endpoints:
            edges_at_point[key].append(eid)

    unused = set(edge_ids)
    while unused:
        first = min(unused, key=edge_ids.index)
        queue = deque([first])
        component: List[str] = []
        while queue:
            eid = queue.popleft()
            if eid not in unused:
                continue
            unused.discard(eid)
            component.append(eid)
            for key in endpoints_by_entity[eid]:
                queue.extend(other for other in edges_at_point[key] if other in unused)
        component.sort(key=edge_ids.index)
        samples: List[Tuple[float, float]] = []
        for eid in component:
            kind = entity_kind(eid)
            pts = _sample_entity(kind, sketch[eid])
            if len(pts) >= 2:
                start_end = [_pt_key(p) for p in (pts[0], pts[-1])]
                dedup = [p for i, p in enumerate(pts) if i == 0 or _pt_key(p) not in start_end or _pt_key(p) != _pt_key(pts[i - 1])]
                samples.extend(dedup)
        profiles.append({
            "index": len(profiles),
            "kind": "chain",
            "entity_ids": component,
            "samples": samples,
            "closed": len(endpoints_by_entity[component[0]]) > 0
            and all(
                sum(1 for eid in component for key in endpoints_by_entity[eid] if key == k) == 2
                for k in {key for eid in component for key in endpoints_by_entity[eid]}
            ),
        })
    return profiles


def _point_in_polygon(point: Tuple[float, float], polygon: Sequence[Tuple[float, float]]) -> bool:
    x, y = point
    inside = False
    n = len(polygon)
    for index in range(n):
        x0, y0 = polygon[index]
        x1, y1 = polygon[(index + 1) % n]
        if (y0 > y) != (y1 > y):
            if x < (x1 - x0) * (y - y0) / (y1 - y0) + x0:
                inside = not inside
    return inside


def _polygon_area(points: Sequence[Tuple[float, float]]) -> float:
    return abs(sum(points[i][0] * points[(i + 1) % len(points)][1] - points[(i + 1) % len(points)][0] * points[i][1] for i in range(len(points))) / 2.0)


def nest_profiles(profiles: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], List[Dict[str, Any]]]]:
    """Group profiles into (outer, holes) trees by point containment."""
    parent: Dict[int, Optional[int]] = {}
    for child, profile in enumerate(profiles):
        best: Optional[int] = None
        best_area = math.inf
        for parent_index, candidate in enumerate(profiles):
            if parent_index == child or len(candidate["samples"]) < 3:
                continue
            if any(_point_in_polygon(pt, candidate["samples"]) for pt in profile["samples"]):
                area = _polygon_area(candidate["samples"])
                if area < best_area:
                    best = parent_index
                    best_area = area
        parent[child] = best
    outers: List[Tuple[Dict[str, Any], List[Dict[str, Any]]]] = []
    for child, profile in enumerate(profiles):
        if parent[child] is None:
            holes = [profiles[i] for i, p in parent.items() if p == child]
            outers.append((profile, holes))
    return outers


# ---------------------------------------------------------------------------
# constraint mapping


class StepEmitter:
    """Emits sketch entity/constraint/promotion/extrude lines for one step."""

    def __init__(self, step: Dict[str, Any], index: int, constraints_mode: str):
        self.step = step
        self.index = index
        self.name = f"f{index}"
        self.constraints_mode = constraints_mode
        self.lines: List[str] = []
        self.pool: Dict[Tuple[float, float], str] = {}
        self.counter = 0
        self.dropped_constraints: List[str] = []

        cs = step.get("coordinate_system") or {}
        euler = cs.get("Euler Angles") or [0.0, 0.0, 0.0]
        translation = cs.get("Translation Vector") or [0.0, 0.0, 0.0]
        x_axis, y_axis = euler_to_axes(euler)
        self.normal = cross(x_axis, y_axis)
        self.plane_literal = (
            "{'origin': " + _vec(translation)
            + ", 'x_axis': " + _vec(x_axis)
            + ", 'y_axis': " + _vec(y_axis) + "}"
        )
        self.sketch = step.get("sketch") or {}
        self.entity_kind_map = {eid: entity_kind(eid) for eid in self.sketch}

    # -- emission ----------------------------------------------------------

    def point(self, x: float, y: float) -> str:
        key = _pt_key((x, y))
        if key in self.pool:
            return self.pool[key]
        self.counter += 1
        pid = f"{self.name}_p{self.counter}"
        self.pool[key] = pid
        self.lines.append(f"s_geo = scad.add_point_rsketch(s_geo, {pid!r}, {_fmt(x)}, {_fmt(y)})")
        return pid

    def emit_sketch(self) -> None:
        self.lines.append(f"s_geo = scad.make_sketch_rsketch(name={self.name!r}, plane={self.plane_literal})")
        for eid, data in self.sketch.items():
            if not isinstance(data, dict):
                continue
            kind = self.entity_kind_map[eid]
            if kind == "line":
                start = self.point(*data["start"])
                end = self.point(*data["end"])
                self.lines.append(f"s_geo = scad.add_line_rsketch(s_geo, {eid!r}, {start!r}, {end!r})")
            elif kind == "circle":
                center = self.point(*data["center"])
                self.lines.append(f"s_geo = scad.add_circle_rsketch(s_geo, {eid!r}, {center!r}, {_fmt(data['radius'])})")
            elif kind == "arc":
                cx, cy = circumcenter(data["start"], data["middle"], data["end"])
                center = self.point(cx, cy)
                start_pt, end_pt = data["start"], data["end"]
                # The sketch promotion sweeps counter-clockwise from start to
                # end, so order the endpoints so that sweep passes through the
                # HistCAD middle point.
                a0 = math.atan2(start_pt[1] - cy, start_pt[0] - cx)
                a1 = math.atan2(end_pt[1] - cy, end_pt[0] - cx)
                am = math.atan2(data["middle"][1] - cy, data["middle"][0] - cx)
                if not ((am - a0) % (2 * math.pi) <= (a1 - a0) % (2 * math.pi)):
                    start_pt, end_pt = end_pt, start_pt
                start = self.point(*start_pt)
                end = self.point(*end_pt)
                self.lines.append(f"s_geo = scad.add_arc_rsketch(s_geo, {eid!r}, {start!r}, {end!r}, {center!r})")
            elif kind == "ellipse":
                cx, cy = data["center"]
                major, minor = float(data["major"]), float(data["minor"])
                theta = math.radians(float(data.get("angle", 0.0)))
                center = self.point(cx, cy)
                major_pt = self.point(cx + major * math.cos(theta), cy + major * math.sin(theta))
                minor_pt = self.point(cx - minor * math.sin(theta), cy + minor * math.cos(theta))
                self.lines.append(f"s_geo = scad.add_ellipse_rsketch(s_geo, {eid!r}, {center!r}, {major_pt!r}, {minor_pt!r})")
            elif kind == "elliptical_arc":
                raise UnsupportedFeature("elliptical_arc entity")
            elif kind == "nurbs":
                knots, mults = knot_multiplicities(data["knots"])
                start = self.point(*data["controls"][0])
                end = self.point(*data["controls"][-1])
                controls = ", ".join(f"({_fmt(c[0])}, {_fmt(c[1])})" for c in data["controls"])
                weights = list(data["weights"]) if data.get("weights") else None
                self.lines.append(
                    f"s_geo = scad.add_bspline_rsketch(s_geo, {eid!r}, {start!r}, {end!r},\n"
                    f"    control_points=[{controls}],\n"
                    f"    degree={int(data['degree'])}, knots={knots!r},\n"
                    f"    multiplicities={mults!r}, weights={weights!r},\n"
                    f"    periodic={bool(data.get('periodic', False))})"
                )

    def _ref(self, target: Any) -> Optional[Tuple[str, str]]:
        if not isinstance(target, str):
            return None
        eid, dot, sub = target.partition(".")
        kind = self.entity_kind_map.get(eid, entity_kind(eid))
        if kind == "unknown":
            return None
        if not dot:
            return (repr(eid), kind) if kind in {"line", "circle", "arc", "ellipse"} else None
        sub_map = {
            "line": {"start", "end"},
            "circle": {"center"},
            "arc": {"start", "end", "center"},
            "ellipse": {"center", "major", "minor"},
            "nurbs": {"start", "end"},
        }.get(kind, set())
        if sub not in sub_map:
            return None
        return repr(f"{eid}.{sub}"), "point"

    def emit_constraints(self) -> List[str]:
        if self.constraints_mode == "off":
            return []
        lines: List[str] = []
        constraints = self.step.get("constraints") or {}
        counter = 0
        for ctype, entries in sorted(constraints.items()):
            if not isinstance(entries, list):
                entries = [entries]
            for entry in entries:
                counter += 1
                label = f"h{counter}_{ctype}"
                lines.extend(self._map_constraint(str(ctype), entry, label))
        return lines

    def _constrain(self, call: str, label: Optional[str] = None) -> List[str]:
        label = label or getattr(self, "_current_label", "h?")
        # tag every emitted constraint with its HistCAD identity so solver
        # diagnostics can name the offending source entry
        return [f"s = scad.{call[:-1]}, constraint_id={label!r})"]

    def _map_constraint(self, ctype: str, entry: Any, label: str = "h?"):
        self._current_label = label
        drop = lambda label: self.dropped_constraints.append(label)  # noqa: E731

        if not isinstance(entry, list):
            drop(ctype)
            return []
        refs = [self._ref(t) for t in entry if isinstance(t, str)]

        if ctype == "Coincident" and len(refs) == 2 and all(r and r[1] == "point" for r in refs):
            return self._constrain(f"constrain_coincident_rsketch(s, {refs[0][0]}, {refs[1][0]})")
        if ctype in {"Horizontal", "Vertical"}:
            fn = "Horizontal" if ctype == "Horizontal" else "Vertical"
            if len(refs) == 2 and all(r and r[1] == "point" for r in refs):
                return self._constrain(f"constrain_points_{fn.lower()}_rsketch(s, {refs[0][0]}, {refs[1][0]})")
            if len(refs) == 1 and refs[0] and refs[0][1] == "line":
                return self._constrain(f"constrain_{fn.lower()}_rsketch(s, {refs[0][0]})")
        if ctype == "Parallel" and len(refs) >= 2:
            chain = [r for r in refs if r and r[1] == "line"]
            if len(chain) == len(refs) and len(chain) >= 2:
                return [
                    c
                    for i, (a, b) in enumerate(zip(chain, chain[1:]))
                    for c in self._constrain(f"constrain_parallel_rsketch(s, {a[0]}, {b[0]})", f"{label}-{i + 2}")
                ]
        if ctype == "Perpendicular" and len(refs) == 2 and all(r and r[1] == "line" for r in refs):
            return self._constrain(f"constrain_perpendicular_rsketch(s, {refs[0][0]}, {refs[1][0]})")
        if ctype == "Equal" and len(refs) >= 2 and all(r for r in refs):
            out: List[str] = []
            ok = True
            for a, b in zip(refs, refs[1:]):
                if {a[1], b[1]} == {"line"}:
                    out.extend(self._constrain(f"constrain_equal_length_rsketch(s, {a[0]}, {b[0]})"))
                elif {a[1], b[1]} <= {"circle", "arc"}:
                    out.extend(self._constrain(f"constrain_equal_radius_rsketch(s, {a[0]}, {b[0]})"))
                else:
                    ok = False
            if ok:
                return out
        if ctype == "Tangent" and len(refs) == 2 and all(r and r[1] in {"line", "circle", "arc"} for r in refs):
            return self._constrain(f"constrain_tangent_rsketch(s, {refs[0][0]}, {refs[1][0]})")
        if ctype == "Concentric" and len(refs) >= 2:
            chain = [r for r in refs if r and r[1] in {"circle", "arc", "ellipse"}]
            if len(chain) == len(refs) and len(chain) >= 2:
                return [
                    c
                    for i, (a, b) in enumerate(zip(chain, chain[1:]))
                    for c in self._constrain(f"constrain_concentric_rsketch(s, {a[0]}, {b[0]})", f"{label}-{i + 2}")
                ]
        if ctype in {"Diameter", "Radius", "MajorRadius", "MinorRadius"} and len(entry) == 2:
            ref = self._ref(entry[0])
            value = eval_value_expr(entry[1]) if not isinstance(entry[1], str) or "." not in entry[1] else eval_value_expr(entry[1])
            if ref and value is not None:
                fn = {
                    "Radius": "constrain_radius_rsketch",
                    "Diameter": "constrain_diameter_rsketch",
                    "MajorRadius": "constrain_major_radius_rsketch",
                    "MinorRadius": "constrain_minor_radius_rsketch",
                }[ctype]
                expected = {"Radius": {"circle", "arc"}, "Diameter": {"circle", "arc"}, "MajorRadius": {"ellipse"}, "MinorRadius": {"ellipse"}}[ctype]
                if ref[1] in expected:
                    return self._constrain(f"{fn}(s, {ref[0]}, {_fmt(value)})")
        if ctype == "Length" and len(entry) == 2:
            ref = self._ref(entry[0])
            if ref and ref[1] == "line":
                value = eval_value_expr(entry[1])
                if value is not None:
                    return self._constrain(f"constrain_length_rsketch(s, {ref[0]}, {_fmt(value)})")
                other = self._ref(entry[1])
                if other and other[1] == "line":
                    return self._constrain(f"constrain_equal_length_rsketch(s, {ref[0]}, {other[0]})")
        if ctype == "Angle" and len(entry) == 3 and all(refs) and all(r[1] == "line" for r in refs[:2]):
            value = eval_value_expr(entry[2])
            if value is not None:
                return self._constrain(f"constrain_angle_rsketch(s, {refs[0][0]}, {refs[1][0]}, {_fmt(value)})")
        if ctype == "Normal" and len(refs) == 2 and all(refs):
            kinds = {r[1] for r in refs}
            if kinds == {"line", "circle"} or kinds == {"line", "arc"}:
                return self._constrain(f"constrain_normal_rsketch(s, {refs[0][0]}, {refs[1][0]})")
        if ctype == "Mirror" and len(entry) == 3:
            a, axis, b = (self._ref(t) for t in entry)
            if a and b and axis and axis[1] == "line" and a[1] == b[1] and a[1] in {"line", "circle", "arc"}:
                return self._constrain(f"constrain_mirror_rsketch(s, {a[0]}, {axis[0]}, {b[0]})")
        if ctype == "Midpoint" and len(entry) == 2:
            if isinstance(entry[1], list) and len(entry[1]) == 2:
                mid, a, b = (self._ref(entry[0]), self._ref(entry[1][0]), self._ref(entry[1][1]))
                if mid and a and b and all(r[1] == "point" for r in (mid, a, b)):
                    return self._constrain(f"constrain_midpoint_points_rsketch(s, {mid[0]}, {a[0]}, {b[0]})")
            else:
                point, target = (self._ref(entry[0]), self._ref(entry[1]))
                if point and target and point[1] == "point" and target[1] == "line":
                    return self._constrain(f"constrain_midpoint_rsketch(s, {point[0]}, {target[0]})")
        if ctype == "Fix" and isinstance(entry, list) and len(entry) == 1:
            ref = self._ref(entry[0])
            if ref:
                return self._constrain(f"constrain_fix_rsketch(s, {ref[0]})")
        if ctype == "Distance" and len(entry) == 3 and isinstance(entry[2], dict):
            payload = entry[2]
            value = eval_value_expr(payload.get("length"))
            direction = str(payload.get("direction", "MINIMUM"))
            pair = [self._ref(t) for t in entry[:2]]
            if value is not None and all(r for r in pair):
                if all(r[1] == "point" for r in pair):
                    fn = {"HORIZONTAL": "distance_x", "VERTICAL": "distance_y"}.get(direction, "distance")
                    return self._constrain(f"constrain_{fn}_rsketch(s, {pair[0][0]}, {pair[1][0]}, {_fmt(abs(value))})")
                if all(r[1] == "line" for r in pair):
                    return self._constrain(f"constrain_line_distance_rsketch(s, {pair[0][0]}, {pair[1][0]}, {_fmt(abs(value))})")
        drop(ctype if len(entry) != 2 else f"{ctype}({len(entry)})")
        return []

    # -- promotion and extrude ---------------------------------------------

    def emit_feature(self) -> Dict[str, Any]:
        self.emit_sketch()
        constraint_lines = self.emit_constraints()

        profiles = classify_profiles(self.sketch)
        groups = nest_profiles(profiles)
        towards = float(self.step.get("towards") or 0.0)
        opposite = float(self.step.get("opposite") or 0.0)
        mode = str(self.step.get("operation"))
        normal_neg = (-self.normal[0], -self.normal[1], -self.normal[2])

        tool_lines: List[str] = []
        tool_vars: List[str] = []
        for island, (outer, holes) in enumerate(groups):
            face_var = f"{self.name}_face{island}"
            inner = f", inner_profiles={[h['index'] for h in holes]}" if holes else ""
            promote = (
                f"scad.make_face_from_sketch_rface(s, profile={outer['index']}{inner})"
            )
            if constraint_lines:
                tool_lines.append(f"try:")
                tool_lines.append(f"    {face_var} = {promote}")
                tool_lines.append(f"except Exception:")
                tool_lines.append(f"    SKETCH_TIER_FALLBACKS.append({self.index!r})")
                tool_lines.append(f"    try:")
                tool_lines.append(f"        _diag = scad.inspect_sketch_rsketchresult(s, strict=False)")
                tool_lines.append(f"        SKETCH_CONFLICTS.append({{")
                tool_lines.append(f"            'feature': {self.index!r},")
                tool_lines.append(f"            'status': _diag.status,")
                tool_lines.append(f"            'dof': _diag.dof,")
                tool_lines.append(f"            'failed_constraints': [d.constraint_id for d in _diag.diagnostics if d.severity == 'error'],")
                tool_lines.append(f"            'warnings': [d.code for d in _diag.diagnostics if d.severity == 'warning'],")
                tool_lines.append(f"        }})")
                tool_lines.append(f"    except Exception as _exc:")
                tool_lines.append(f"        SKETCH_CONFLICTS.append({{'feature': {self.index!r}, 'status': 'inspect_failed', 'failed_constraints': [], 'warnings': [str(_exc)[:120]]}})")
                tool_lines.append(
                    f"    {face_var} = scad.make_face_from_sketch_rface(s_geo, profile={outer['index']}{inner})"
                )
            else:
                tool_lines.append(f"{face_var} = {promote}")
            if towards > 0 and opposite > 0:
                tool_var = f"{self.name}_tool{island}"
                tool_lines.append(
                    f"{tool_var} = scad.union_rsolid(\n"
                    f"    scad.extrude_rsolid(profile={face_var}, direction={_vec(self.normal)}, distance={_fmt(towards)}),\n"
                    f"    [scad.extrude_rsolid(profile={face_var}, direction={_vec(normal_neg)}, distance={_fmt(opposite)})])"
                )
                tool_vars.append(tool_var)
            elif towards > 0 or opposite > 0:
                distance = towards if towards > 0 else opposite
                direction = self.normal if towards > 0 else normal_neg
                tool_var = f"{self.name}_tool{island}"
                tool_lines.append(
                    f"{tool_var} = scad.extrude_rsolid(profile={face_var}, direction={_vec(direction)}, distance={_fmt(distance)})"
                )
                tool_vars.append(tool_var)
            else:
                raise UnsupportedFeature("zero-extent extrude")

        return {
            "sketch_lines": self.lines,
            "constraint_lines": constraint_lines,
            "tool_lines": tool_lines,
            "tool_vars": tool_vars,
            "mode": mode,
            "dropped": self.dropped_constraints,
        }


class UnsupportedFeature(Exception):
    pass


_MODE_ROLES = {"NewBody": "build", "Join": "add", "Cut": "subtract", "Intersect": "intersect"}


def translate_steps(steps: Sequence[Dict[str, Any]], uid: str, constraints_mode: str = "auto") -> str:
    lines: List[str] = [
        f'"""FTC source generated from HistCAD {uid}."""',
        "",
        "import simplecadapi as scad",
        "",
        "BODIES = None  # all solid bodies before single-solid merge (harness)",
        "SKETCH_TIER_FALLBACKS = []  # feature indexes whose constrained solve fell back",
        "SKETCH_CONFLICTS = []  # per-fallback solver diagnostics (dataset audit)",
        "",
        "",
        "def _merge_bodies(bodies):",
        "    result = bodies[0]",
        "    for extra in bodies[1:]:",
        "        try:",
        "            result = scad.union_rsolid(result, [extra])",
        "        except Exception:",
        "            pass  # disjoint bodies stay outside the single-solid contract",
        "    return result",
        "",
        "",
        f"@scad.part(id={'histcad-' + uid.replace('/', '-')!r}, revision='1.0.0')",
        "def build() -> scad.Part:",
    ]
    notes: List[str] = []
    body_var = "body"
    first_feature = True
    all_dropped: List[str] = []

    for index, step in enumerate(steps):
        mode = str(step.get("operation"))
        role = _MODE_ROLES.get(mode, "build")
        emitter = StepEmitter(step, index, constraints_mode=constraints_mode)
        try:
            feature = emitter.emit_feature()
        except UnsupportedFeature as exc:
            notes.append(f"step {index}: unsupported ({exc})")
            continue
        all_dropped.extend(feature["dropped"])

        if constraints_mode == "off" or not feature["constraint_lines"]:
            tier = "profile=geometry"
        elif feature["dropped"]:
            tier = "profile=sketch+geometry (partial constraints)"
        else:
            tier = "profile=sketch (fallback=geometry)"
        if feature["dropped"]:
            notes.append(f"feature {index}: unmapped constraint kinds {sorted(set(feature['dropped']))}")
        slug = f"{mode.lower()}-{index + 1}"
        lines.append(f"    # ---- feature: {slug} ({role}, {tier}) ----")
        lines.extend(f"    {line}" for line in feature["sketch_lines"])
        lines.append("    s = s_geo")
        lines.extend(f"    {line}" for line in feature["constraint_lines"])
        lines.extend(f"    {line}" for line in feature["tool_lines"])
        tools = feature["tool_vars"]
        tool_list = "[" + ", ".join(tools) + "]"
        if mode == "NewBody":
            if first_feature:
                lines.append(f"    bodies = list({tool_list})")
                first_feature = False
            else:
                lines.append(f"    bodies.extend({tool_list})")
        elif mode == "Join":
            lines.append(f"    _merged = False")
            lines.append(f"    _next = []")
            lines.append(f"    for _b in bodies:")
            lines.append(f"        try:")
            lines.append(f"            _next.append(scad.union_rsolid(_b, {tool_list}))")
            lines.append(f"            _merged = True")
            lines.append(f"        except Exception:")
            lines.append(f"            _next.append(_b)")
            lines.append(f"    bodies = _next")
            lines.append(f"    if not _merged:")
            lines.append(f"        bodies.extend({tool_list})")
        elif mode == "Cut":
            lines.append(f"    bodies = [scad.cut_rsolid(_b, {tool_list}) for _b in bodies]")
        elif mode == "Intersect":
            lines.append(f"    bodies = [scad.intersect_rsolid(_b, {tools[0]}) for _b in bodies]")

    lines.append("    global BODIES")
    lines.append("    BODIES = list(bodies)")
    lines.append("    return _merge_bodies(bodies)")
    header_notes = [f"    # {note}" for note in notes]
    return "\n".join(lines[:6] + header_notes + lines[6:]) + "\n"


# ---------------------------------------------------------------------------
# validation harness


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_file", nargs="?", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--constraints", choices=["auto", "off", "on"], default="auto")
    args = parser.parse_args(argv)

    if not args.json_file:
        parser.error("provide a json file (tar batch mode lives in histcad_validate.py)")
    steps = json.loads(args.json_file.read_text())
    source = translate_steps(steps, args.json_file.stem, constraints_mode=args.constraints)
    out_path = args.out or args.json_file.with_suffix(".ftc.py")
    out_path.write_text(source)
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
