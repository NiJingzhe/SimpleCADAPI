"""Thin OCP-native curve and wire builders."""

from __future__ import annotations

import math
from typing import Iterable, Optional, Sequence

from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
from OCP.BRepLib import BRepLib
from OCP.GC import GC_MakeArcOfCircle, GC_MakeCircle
from OCP.GCE2d import GCE2d_MakeSegment
from OCP.GeomAPI import GeomAPI_Interpolate, GeomAPI_PointsToBSpline
from OCP.Geom2d import Geom2d_Line
from OCP.Geom import Geom_ConicalSurface, Geom_CylindricalSurface
from OCP.TColgp import TColgp_Array1OfPnt, TColgp_Array1OfVec, TColgp_HArray1OfPnt
from OCP.TColStd import TColStd_HArray1OfBoolean
from OCP.gp import (
    gp_Ax2,
    gp_Ax3,
    gp_Circ,
    gp_Dir,
    gp_Dir2d,
    gp_Pnt,
    gp_Pnt2d,
    gp_Vec,
)

from .spline_fit import select_fit_samples


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
    points: Iterable[Sequence[float]],
    tangents: Optional[Iterable[Sequence[float]]] = None,
):
    pts = list(points)
    fit_pts = select_fit_samples(pts, target_count=6)
    arr = TColgp_Array1OfPnt(1, len(fit_pts))
    for idx, point in enumerate(fit_pts, start=1):
        arr.SetValue(idx, _pnt(point))

    if tangents:
        tangent_list = list(tangents)
        h_points = TColgp_HArray1OfPnt(1, len(fit_pts))
        for idx, point in enumerate(fit_pts, start=1):
            h_points.SetValue(idx, _pnt(point))
        fit_tangents = list(tangent_list)
        if len(fit_tangents) != len(fit_pts):
            fit_tangents = []
        h_tangents = TColgp_Array1OfVec(1, len(fit_tangents))
        flags = TColStd_HArray1OfBoolean(1, len(fit_tangents))
        for idx, tangent in enumerate(fit_tangents, start=1):
            h_tangents.SetValue(
                idx, gp_Vec(float(tangent[0]), float(tangent[1]), float(tangent[2]))
            )
            flags.SetValue(idx, True)
        interp = GeomAPI_Interpolate(h_points, False, 1e-6)
        interp.Load(h_tangents, flags, True)
        interp.Perform()
        if not interp.IsDone():
            raise ValueError("OCP interpolation failed")
        return BRepBuilderAPI_MakeEdge(interp.Curve()).Edge()

    bspline = GeomAPI_PointsToBSpline(arr)
    return BRepBuilderAPI_MakeEdge(bspline.Curve()).Edge()


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
