"""OCP-native mesh/shell construction and tessellation helpers."""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon, BRepBuilderAPI_MakeSolid
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.Poly import Poly_Triangulation
from OCP.TopAbs import TopAbs_FORWARD, TopAbs_REVERSED
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS, TopoDS_Face, TopoDS_Shell
from OCP.gp import gp_Pnt

from .ocp_properties import bounding_box
from .ocp_topology import faces_of


def make_triangle_face(points: Sequence[Sequence[float]]) -> TopoDS_Face:
    if len(points) != 3:
        raise ValueError("Triangle face requires exactly three points")
    polygon = BRepBuilderAPI_MakePolygon()
    for p in points:
        polygon.Add(gp_Pnt(float(p[0]), float(p[1]), float(p[2])))
    polygon.Close()
    if not polygon.IsDone():
        raise ValueError("OCP polygon builder failed")
    face = BRepBuilderAPI_MakeFace(polygon.Wire(), True)
    if not face.IsDone():
        raise ValueError("OCP triangle face builder failed")
    return face.Face()


def shell_metric(shell) -> tuple[int, float]:
    bb = bounding_box(shell)
    volume = bb.xlen * bb.ylen * bb.zlen
    return (len(faces_of(shell)), float(volume))


def shell_is_closed(shell) -> bool:
    return bool(TopoDS.Shell_s(shell).Closed())


def solid_from_shell(shell):
    maker = BRepBuilderAPI_MakeSolid(TopoDS.Shell_s(shell))
    if not maker.IsDone():
        raise ValueError("OCP solid-from-shell builder failed")
    return maker.Solid()


def tessellate_face(face: TopoDS_Face, tolerance: float = 0.35, angular_tolerance: float = 0.22):
    mesh = BRepMesh_IncrementalMesh(face, float(tolerance), False, float(angular_tolerance), True)
    mesh.Perform()
    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(face, loc)
    if tri is None:
        return [], []
    trsf = loc.Transformation()
    vertices = []
    for idx in range(1, tri.NbNodes() + 1):
        p = tri.Node(idx).Transformed(trsf)
        vertices.append((float(p.X()), float(p.Y()), float(p.Z())))
    triangles = []
    reversed_face = face.Orientation() == TopAbs_REVERSED
    for idx in range(1, tri.NbTriangles() + 1):
        a, b, c = tri.Triangle(idx).Get()
        if reversed_face:
            triangles.append((a - 1, c - 1, b - 1))
        else:
            triangles.append((a - 1, b - 1, c - 1))
    return vertices, triangles
