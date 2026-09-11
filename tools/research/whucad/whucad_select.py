#!/usr/bin/env python3
"""Translate WHUCAD Topo/Select references into FTC ``ql`` selector source.

WHUCAD references topology by history — "face #no of the #body_no feature of
type body_type", plus derived edges ("the edge shared by these two faces").
The translator resolves those references analytically from the decoded
construction history (it already knows every face it emits) and emits a
``ql`` geometric-predicate selector — the same pattern as the repository's
hand-written examples. Resolution here is bookkeeping of known geometry, not
solving; whether the emitted selector matches the intended face at build time
is a question for whucad_validate.py.

Canonical face numbering (calibrated against the dataset's own CATIA
reconstruction and the packaged BRep truth — see README):
    no == 0  lateral face swept from the sketch wire (the Select carries the
             ``Wire/Sketch`` reference in ``operation_list``)
    no == 1  near cap   (cap on the sketch plane side)
    no == 2  far cap    (cap at the far end of the extrusion)
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, List, Optional, Sequence, Tuple

import numpy as np

from whucad_vec import Circle, ExtrudeFeature, Line, RevolveFeature, Select

_TOL = 1e-4          # predicate tolerance, normalized-model units (bbox ~1.5)


# ---------------------------------------------------------------------------
# face/edge descriptors (analytic facts about faces the translator emits)


@dataclass
class PlaneFace:
    point: np.ndarray        # a point on the plane (the cap centroid lies on it)
    normal: np.ndarray
    area: float
    kind: str = "PLANE"


@dataclass
class CylinderFace:
    center: np.ndarray       # face centroid: axis point at mid height
    axis: np.ndarray
    radius: float
    height: float
    kind: str = "CYLINDER"

    @property
    def area(self) -> float:
        return 2.0 * math.pi * self.radius * self.height


@dataclass
class EdgeDesc:
    kind: str                # "CIRCLE" | "LINE"
    center: np.ndarray       # circle center / segment midpoint
    length: float
    direction: Optional[np.ndarray] = None  # LINE only
    reference_normal: Optional[np.ndarray] = None  # chamfer reference face


def circle_edge(center, radius: float, reference_normal=None) -> EdgeDesc:
    return EdgeDesc("CIRCLE", np.asarray(center, dtype=float),
                    2.0 * math.pi * radius, None, reference_normal)


FaceDesc = Any  # PlaneFace | CylinderFace


def to3d(plan, p2d) -> np.ndarray:
    return (np.asarray(plan.plane_origin, dtype=float)
            + plan.plane_x_axis * float(p2d[0]) + plan.plane_y_axis * float(p2d[1]))


# ---------------------------------------------------------------------------
# canonical faces of an extrude-like feature


def loop_area(points: Sequence[Tuple[float, float]]) -> float:
    """|area| of a polygon sample of a loop (the predicate needs a stable
    fingerprint within tolerance, not an exact integral)."""
    pts = np.asarray(points, dtype=float)
    if len(pts) < 3:
        return 0.0
    x, y = pts[:, 0], pts[:, 1]
    return abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1))) / 2.0)


def curve_samples(curve, n: int = 24) -> List[Tuple[float, float]]:
    if isinstance(curve, Line):
        return [tuple(curve.start_point), tuple(curve.end_point)]
    if isinstance(curve, Circle):
        c, r = curve.center, curve.radius
        return [(c[0] + r * math.cos(2 * math.pi * i / n),
                 c[1] + r * math.sin(2 * math.pi * i / n)) for i in range(n)]
    pts = []
    a0 = curve.start_arc
    span = (curve.end_arc - curve.start_arc) % (2.0 * math.pi)
    for i in range(n):
        a = a0 + span * i / (n - 1)
        pts.append((curve.center[0] + curve.radius * math.cos(a),
                    curve.center[1] + curve.radius * math.sin(a)))
    return pts


def _loop_area(plan, loop) -> float:
    samples: List[Tuple[float, float]] = []
    for curve in loop.curves:
        samples.extend(curve_samples(curve))
    return loop_area(samples)


def _wire_curve(feature, wire_no: int):
    """Curve #wire_no (1-based, flat across the profile's loops)."""
    curves = [c for loop in feature.sketch.profile.loops for c in loop.curves]
    if not 1 <= wire_no <= len(curves):
        raise UnsupportedSelect(f"wire #{wire_no} out of range")
    return curves[wire_no - 1]


def _lateral_face(feature: ExtrudeFeature, wire_no: int) -> FaceDesc:
    """The face swept from sketch curve #wire_no: a cylinder wall for a
    circle, a plane wall for a line."""
    plan = feature.sketch
    curve = _wire_curve(feature, wire_no)
    low, high = extrude_span(feature)
    height = high - low
    mid_offset = (low + high) / 2.0
    if isinstance(curve, Circle):
        center3 = to3d(plan, curve.center)
        mid = center3 + plan.plane_normal * mid_offset
        return CylinderFace(mid, plan.plane_normal, float(curve.radius), abs(height))
    if isinstance(curve, Line):
        p0 = to3d(plan, curve.start_point)
        p1 = to3d(plan, curve.end_point)
        direction = p1 - p0
        length = float(np.linalg.norm(direction))
        if length < 1e-9:
            raise UnsupportedSelect("degenerate wire line")
        direction = direction / length
        # outward normal of a CCW loop wall: line direction × extrude normal
        normal = np.cross(direction, plan.plane_normal)
        mid = p0 + direction * (length / 2.0) + plan.plane_normal * mid_offset
        return PlaneFace(mid, normal, length * abs(height))
    raise UnsupportedSelect("lateral face over an arc wire")


def extrude_span(feature: ExtrudeFeature) -> Tuple[float, float]:
    """Signed span of the extrusion along the plane normal: [−e2, +e1].
    Negative extents (inverted pads) cross the sketch plane."""
    return (-float(feature.extent_two), float(feature.extent_one))


def cap_face_desc(feature: ExtrudeFeature, face_no: int) -> PlaneFace:
    """Near (1) / far (2) cap face descriptor — no lateral construction, so
    polygon-loop pads resolve without a lateral-wall form."""
    plan = feature.sketch
    area = _loop_area(plan, plan.profile.loops[0])
    low, high = extrude_span(feature)
    n = plan.plane_normal
    if face_no == 1:
        return PlaneFace(plan.plane_origin + n * low, -n, area)
    if face_no == 2:
        return PlaneFace(plan.plane_origin + n * high, n, area)
    raise UnsupportedSelect(f"cap no={face_no}")


def extrude_face_descs(feature: ExtrudeFeature, wire_no: int = 1) -> List[FaceDesc]:
    """[lateral, near cap, far cap] of an extrude feature."""
    lateral = _lateral_face(feature, wire_no)
    return [lateral, cap_face_desc(feature, 1), cap_face_desc(feature, 2)]


class UnsupportedSelect(Exception):
    pass


# ---------------------------------------------------------------------------
# feature registry (body_no → decoded feature, 1-based within each body kind)


class FeatureRegistry:
    """Maps (body_type, body_no) onto the features decoded before the current
    one — the same history the dataset's references point into."""

    _BODY_KIND = {"Pad": "Ext", "Shaft": "Rev", "Pocket": "Pocket", "Groove": "Groove"}

    def __init__(self, features: Sequence[object]):
        self._by_kind: dict = {}
        self._all = list(features)

    def lookup(self, select: Select) -> object:
        kind = self._BODY_KIND.get(select.body_type)
        if kind is None:
            raise UnsupportedSelect(f"body_type {select.body_type}")
        bucket = [f for f in self._all if getattr(f, "kind", None) == kind]
        if not 1 <= select.body_no <= len(bucket):
            raise UnsupportedSelect(f"{select.body_type}#{select.body_no} out of range")
        return bucket[select.body_no - 1]


# ---------------------------------------------------------------------------
# select tree resolution


def resolve_face(select: Select, registry: FeatureRegistry) -> Tuple[object, FaceDesc, int]:
    """Resolve a Face leaf select to (source feature, face descriptor, no)."""
    if select.operation_list:
        wire_ref = select.operation_list[0]
        if select.no == 0 and wire_ref.select_type == "Wire":
            feature = registry.lookup(select)
            if not isinstance(feature, (ExtrudeFeature, RevolveFeature)):
                raise UnsupportedSelect("wire face of a non-sketch feature")
            if isinstance(feature, ExtrudeFeature):
                return feature, _lateral_face(feature, wire_ref.no), 0
            raise UnsupportedSelect("lateral face of a revolve")
        raise UnsupportedSelect(f"derived face form no={select.no}")
    feature = registry.lookup(select)
    if not isinstance(feature, (ExtrudeFeature, RevolveFeature)):
        raise UnsupportedSelect(f"face of {select.body_type}")
    if select.body_type != "Pad":
        raise UnsupportedSelect(f"face numbering of {select.body_type}")
    if not 0 <= select.no <= 2:
        raise UnsupportedSelect(f"face no={select.no}")
    if len(feature.sketch.profile.loops) != 1:
        raise UnsupportedSelect("cap numbering of a multi-loop pad")
    return feature, cap_face_desc(feature, select.no), select.no


def lateral_boundary_edges(select: Select, registry: FeatureRegistry) -> List[EdgeDesc]:
    """A Face leaf naming the lateral wall (no == 0) appears two ways: with a
    Wire reference (any wall) or bare on single-circle pads. Both mean
    "every edge of that wall" — cap joints + vertical corners for a line
    wall, the rims for a circular wall."""
    if select.no != 0:
        raise UnsupportedSelect("lateral leaf form")
    feature = registry.lookup(select)
    if not isinstance(feature, ExtrudeFeature):
        raise UnsupportedSelect("lateral face of a revolve")
    if select.operation_list:
        if select.operation_list[0].select_type != "Wire":
            raise UnsupportedSelect("lateral leaf form")
        return wire_boundary_edges(feature, select.operation_list[0].no)
    loops = feature.sketch.profile.loops
    if len(loops) != 1 or len(loops[0].curves) != 1 or not isinstance(loops[0].curves[0], Circle):
        raise UnsupportedSelect("lateral leaf on a multi-curve pad")
    return wire_boundary_edges(feature, 1)


def wire_boundary_edges(feature: ExtrudeFeature, wire_no: int) -> List[EdgeDesc]:
    """All boundary edges of the wall swept from sketch curve #wire_no."""
    plan = feature.sketch
    curve = _wire_curve(feature, wire_no)
    low, high = extrude_span(feature)
    n = plan.plane_normal
    if isinstance(curve, Circle):
        center3 = to3d(plan, curve.center)
        return [circle_edge(center3 + n * low, float(curve.radius), -n),
                circle_edge(center3 + n * high, float(curve.radius), n)]
    if isinstance(curve, Line):
        p0 = to3d(plan, curve.start_point)
        p1 = to3d(plan, curve.end_point)
        wall_normal = np.cross((p1 - p0) / np.linalg.norm(p1 - p0), n)
        descs = []
        for offset, ref in ((low, -n), (high, n)):
            a = p0 + n * offset
            b = p1 + n * offset
            direction = (b - a) / np.linalg.norm(b - a)
            descs.append(EdgeDesc("LINE", (a + b) / 2.0, float(np.linalg.norm(b - a)),
                                  direction, ref))
        for point in (curve.start_point, curve.end_point):
            base = to3d(plan, point)
            a = base + n * low
            b = base + n * high
            direction = (b - a) / np.linalg.norm(b - a)
            descs.append(EdgeDesc("LINE", (a + b) / 2.0, float(np.linalg.norm(b - a)),
                                  direction, wall_normal))
        return descs
    raise UnsupportedSelect("wall over an arc wire")


def resolve_edge(select: Select, registry: FeatureRegistry) -> EdgeDesc:
    """Edge select: body_type None, operation_list = the two bounding faces.
    The span is taken from the wire geometry at the referenced cap."""
    if select.select_type != "Edge" or len(select.operation_list) != 2:
        raise UnsupportedSelect("edge form")
    subs = select.operation_list
    resolved = [resolve_face(sub, registry) for sub in subs]
    (fa, da, na), (fb, db, nb) = resolved
    if isinstance(da, CylinderFace) and isinstance(db, CylinderFace):
        raise UnsupportedSelect("edge between two cylinder walls")
    cylinder = next((d for d in (da, db) if isinstance(d, CylinderFace)), None)
    if cylinder is not None:
        plane = db if isinstance(da, CylinderFace) else da
        return _circle_edge_of(cylinder, plane,
                               reference_normal=_cap_normal(resolved))
    if isinstance(da, PlaneFace) and isinstance(db, PlaneFace):
        wall_subs = [(sub, res) for sub, res in zip(subs, resolved)
                     if res[2] == 0 and sub.operation_list]
        if len(wall_subs) == 2:
            return _wall_wall_edge(wall_subs[0][1][0], wall_subs[1][1][0],
                                   [sub.operation_list[0].no for sub, _ in wall_subs],
                                   reference_normal=_cap_normal(resolved))
        for sub, (feature, desc, no) in zip(subs, resolved):
            if no == 0 and sub.operation_list:
                wire_no = sub.operation_list[0].no
                cap_no = nb if no == na else na
                if cap_no not in (1, 2):
                    raise UnsupportedSelect("wall/wall edge")
                return wire_line_edge(feature, wire_no, cap_no,
                                      reference_normal=_cap_normal(resolved))
        raise UnsupportedSelect("line edge without cap/wire pair")
    raise UnsupportedSelect("edge between " + da.kind + " and " + db.kind)


def _wall_wall_edge(feature_a: ExtrudeFeature, feature_b: ExtrudeFeature,
                    wire_nos: List[int], reference_normal) -> EdgeDesc:
    """Vertical corner edge where two adjacent walls meet: the shared wire
    endpoint of the two referenced lines (same pad), spanning the extrusion."""
    if feature_a is not feature_b:
        raise UnsupportedSelect("wall/wall edge across features")
    plan = feature_a.sketch
    curve_a = _wire_curve(feature_a, wire_nos[0])
    curve_b = _wire_curve(feature_a, wire_nos[1])
    if not (isinstance(curve_a, Line) and isinstance(curve_b, Line)):
        raise UnsupportedSelect("wall/wall edge over a curved wire")
    shared = _shared_point(curve_a, curve_b)
    if shared is None:
        raise UnsupportedSelect("wall lines do not share an endpoint")
    base = to3d(plan, shared)
    low, high = extrude_span(feature_a)
    a = base + plan.plane_normal * low
    b = base + plan.plane_normal * high
    direction = (b - a) / np.linalg.norm(b - a)
    return EdgeDesc("LINE", (a + b) / 2.0, float(np.linalg.norm(b - a)),
                    direction, reference_normal)


def _shared_point(curve_a: Line, curve_b: Line, tol: float = 1e-6):
    for pa in (curve_a.start_point, curve_a.end_point):
        for pb in (curve_b.start_point, curve_b.end_point):
            if abs(pa[0] - pb[0]) <= tol and abs(pa[1] - pb[1]) <= tol:
                return (float(pa[0]), float(pa[1]))
    return None


def _cap_normal(resolved) -> Optional[np.ndarray]:
    """Convention: the cap face anchors the chamfer's first leg when one of
    the two bounding faces is a cap; otherwise the planar face anchors (the
    vector itself does not record the anchoring — CATIA resolved it from
    edge orientation; see README)."""
    for _, desc, no in resolved:
        if isinstance(desc, PlaneFace) and no in (1, 2):
            return desc.normal
    for _, desc, _ in resolved:
        if isinstance(desc, PlaneFace):
            return desc.normal
    return None


def _circle_edge_of(cyl: CylinderFace, plane: PlaneFace, reference_normal=None) -> EdgeDesc:
    n = plane.normal
    d = float(np.dot(plane.point, n))
    denom = float(np.dot(cyl.axis, n))
    if abs(denom) < 1e-9:
        # cylinder axis parallel to the plane: no circle intersection
        raise UnsupportedSelect("cylinder axis parallel to plane")
    t = (d - float(np.dot(cyl.center, n))) / denom
    center = cyl.center + cyl.axis * t
    return circle_edge(center, cyl.radius, reference_normal=reference_normal)


def wire_line_edge(feature: ExtrudeFeature, wire_no: int, cap_no: int,
                   reference_normal) -> EdgeDesc:
    """The edge between wall(curve #wire_no) and cap(cap_no) of a pad whose
    referenced wire curve is a line."""
    plan = feature.sketch
    curve = _wire_curve(feature, wire_no)
    if not isinstance(curve, Line):
        raise UnsupportedSelect("wall wire is not a single line")
    p0 = to3d(plan, curve.start_point)
    p1 = to3d(plan, curve.end_point)
    low, high = extrude_span(feature)
    offset = plan.plane_normal * (high if cap_no == 2 else low)
    p0, p1 = p0 + offset, p1 + offset
    center = (p0 + p1) / 2.0
    direction = p1 - p0
    length = float(np.linalg.norm(direction))
    return EdgeDesc("LINE", center, length, direction / length, reference_normal)


def cap_boundary_edge(feature: ExtrudeFeature, face_no: int) -> EdgeDesc:
    """Boundary circle of cap face `face_no` (1=near, 2=far) of a circular
    single-loop pad; used when a chamfer/fillet selects the cap face."""
    loop = feature.sketch.profile.loops[0]
    if len(loop.curves) != 1 or not isinstance(loop.curves[0], Circle):
        raise UnsupportedSelect("cap boundary of a non-circular loop")
    circle = loop.curves[0]
    center3 = to3d(feature.sketch, circle.center)
    n = feature.sketch.plane_normal
    low, high = extrude_span(feature)
    if face_no == 1:
        center, normal = center3 + n * low, -n
    elif face_no == 2:
        center, normal = center3 + n * high, n
    else:
        raise UnsupportedSelect(f"cap no={face_no}")
    return circle_edge(center, float(circle.radius), reference_normal=normal)


# ---------------------------------------------------------------------------
# ql source emission


def face_predicate_lines(var: str, desc: FaceDesc, indent: str) -> List[str]:
    """ql.faces().where(...) chain that pins the described face."""
    lines = [f"{var} = (", f"{indent}ql.faces()",
             f'{indent}.where(ql.prop("geom.type", "==", "{desc.kind}"))']
    if isinstance(desc, PlaneFace):
        for axis, value in zip("xyz", desc.normal):
            lines.append(f'{indent}.where(ql.prop("geom.normal.{axis}", ">=", {value - _TOL:.9f}))')
            lines.append(f'{indent}.where(ql.prop("geom.normal.{axis}", "<=", {value + _TOL:.9f}))')
        # the centroid of a planar face lies on its plane
        axis = int(np.argmax(np.abs(desc.normal)))
        value = float(np.dot(desc.point, desc.normal))
        lines.append(f'{indent}.where(ql.prop("geom.center.{"xyz"[axis]}", ">=", {value - _TOL:.9f}))')
        lines.append(f'{indent}.where(ql.prop("geom.center.{"xyz"[axis]}", "<=", {value + _TOL:.9f}))')
    else:
        for axis, value in zip("xyz", desc.center):
            lines.append(f'{indent}.where(ql.prop("geom.center.{axis}", ">=", {value - _TOL:.9f}))')
            lines.append(f'{indent}.where(ql.prop("geom.center.{axis}", "<=", {value + _TOL:.9f}))')
    lines.append(f'{indent}.where(ql.prop("geom.area", ">=", {desc.area * 0.98:.9f}))')
    lines.append(f'{indent}.where(ql.prop("geom.area", "<=", {desc.area * 1.02:.9f}))')
    lines.append(f"{indent})")
    return lines


def edge_predicate_lines(var: str, desc: EdgeDesc, indent: str) -> List[str]:
    lines = [f"{var} = (", f"{indent}ql.edges()",
             f'{indent}.where(ql.prop("geom.type", "==", "{desc.kind}"))']
    for axis, value in zip("xyz", desc.center):
        lines.append(f'{indent}.where(ql.prop("geom.center.{axis}", ">=", {value - _TOL:.9f}))')
        lines.append(f'{indent}.where(ql.prop("geom.center.{axis}", "<=", {value + _TOL:.9f}))')
    lines.append(f'{indent}.where(ql.prop("geom.length", ">=", {desc.length * 0.98:.9f}))')
    lines.append(f'{indent}.where(ql.prop("geom.length", "<=", {desc.length * 1.02:.9f}))')
    lines.append(f"{indent})")
    return lines
