"""Thin OCP-native curve and wire builders."""

from __future__ import annotations

import math
from typing import Any, Iterable, Optional, Sequence

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepLib import BRepLib
from OCP.GC import GC_MakeArcOfCircle, GC_MakeCircle
from OCP.GCE2d import GCE2d_MakeSegment
from OCP.Geom import Geom_BSplineCurve
from OCP.Geom2d import Geom2d_Line
from OCP.Geom import Geom_ConicalSurface, Geom_CylindricalSurface
from OCP.TColgp import TColgp_Array1OfPnt
from OCP.TColStd import TColStd_Array1OfInteger, TColStd_Array1OfReal
from OCP.gp import (
    gp_Ax2,
    gp_Ax3,
    gp_Circ,
    gp_Dir,
    gp_Dir2d,
    gp_Pnt,
    gp_Pnt2d,
)


def _pnt(value: Sequence[float]) -> gp_Pnt:
    return gp_Pnt(float(value[0]), float(value[1]), float(value[2]))


def _dir(value: Sequence[float]) -> gp_Dir:
    return gp_Dir(float(value[0]), float(value[1]), float(value[2]))


def make_line_edge(start: Sequence[float], end: Sequence[float]):
    return BRepBuilderAPI_MakeEdge(_pnt(start), _pnt(end)).Edge()


def make_circle_edge(center: Sequence[float], radius: float, normal: Sequence[float]):
    geom = GC_MakeCircle(gp_Ax2(_pnt(center), _dir(normal)), float(radius)).Value()
    return BRepBuilderAPI_MakeEdge(geom).Edge()


def make_arc_three_point_edge(
    start: Sequence[float], middle: Sequence[float], end: Sequence[float]
):
    geom = GC_MakeArcOfCircle(_pnt(start), _pnt(middle), _pnt(end)).Value()
    return BRepBuilderAPI_MakeEdge(geom).Edge()


def make_arc_angle_edge(
    center: Sequence[float],
    radius: float,
    start_angle: float,
    end_angle: float,
    normal: Sequence[float],
):
    circ = gp_Circ(gp_Ax2(_pnt(center), _dir(normal)), float(radius))
    geom = GC_MakeArcOfCircle(circ, float(start_angle), float(end_angle), True).Value()
    return BRepBuilderAPI_MakeEdge(geom).Edge()


def make_bspline_edge(
    *,
    control_points: Sequence[Sequence[float]],
    degree: int,
    knots: Sequence[float],
    multiplicities: Sequence[int],
    weights: Optional[Sequence[float]] = None,
    periodic: bool = False,
):
    poles = TColgp_Array1OfPnt(1, len(control_points))
    for idx, point in enumerate(control_points, start=1):
        poles.SetValue(idx, _pnt(point))

    knot_array = TColStd_Array1OfReal(1, len(knots))
    for idx, knot in enumerate(knots, start=1):
        knot_array.SetValue(idx, float(knot))

    mult_array = TColStd_Array1OfInteger(1, len(multiplicities))
    for idx, multiplicity in enumerate(multiplicities, start=1):
        mult_array.SetValue(idx, int(multiplicity))

    if weights is None:
        curve = Geom_BSplineCurve(
            poles,
            knot_array,
            mult_array,
            int(degree),
            bool(periodic),
        )
    else:
        weight_array = TColStd_Array1OfReal(1, len(weights))
        for idx, weight in enumerate(weights, start=1):
            weight_array.SetValue(idx, float(weight))
        curve = Geom_BSplineCurve(
            poles,
            weight_array,
            knot_array,
            mult_array,
            int(degree),
            bool(periodic),
        )
    return BRepBuilderAPI_MakeEdge(curve).Edge()


def make_wire_from_edges(edges: Iterable[Any]):
    builder = BRepBuilderAPI_MakeWire()
    for edge in edges:
        builder.Add(edge)
    return builder.Wire()


def make_polyline_wire(points: Iterable[Sequence[float]], closed: bool = False):
    pts = list(points)
    edges = [make_line_edge(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    if closed and len(pts) > 2:
        edges.append(make_line_edge(pts[-1], pts[0]))
    return make_wire_from_edges(edges)


def make_helix_wire(
    pitch: float,
    height: float,
    radius: float,
    center: Sequence[float],
    direction: Sequence[float],
):
    geom_surf = Geom_CylindricalSurface(
        gp_Ax3(_pnt(center), _dir(direction)), float(radius)
    )
    geom_line = Geom2d_Line(gp_Pnt2d(0.0, 0.0), gp_Dir2d(2 * math.pi, float(pitch)))
    n_turns = float(height) / float(pitch)
    u_start = geom_line.Value(0.0)
    u_stop = geom_line.Value(
        n_turns * math.sqrt((2 * math.pi) ** 2 + float(pitch) ** 2)
    )
    geom_seg = GCE2d_MakeSegment(u_start, u_stop).Value()
    edge = BRepBuilderAPI_MakeEdge(geom_seg, geom_surf).Edge()
    wire = BRepBuilderAPI_MakeWire(edge).Wire()
    BRepLib.BuildCurves3d_s(wire, 1e-6, MaxSegment=2000)
    return wire
