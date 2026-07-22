"""OCP-native mesh/shell construction and tessellation helpers."""

from __future__ import annotations

from typing import Iterable, List, Sequence, Tuple

from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_MakePolygon,
    BRepBuilderAPI_MakeSolid,
    BRepBuilderAPI_Transform,
)
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepTools import BRepTools
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
    vertices, triangles, _corner_normals = tessellate_face_with_normals(
        face,
        tolerance=tolerance,
        angular_tolerance=angular_tolerance,
    )
    return vertices, triangles


def tessellate_face_with_normals(
    face: TopoDS_Face,
    tolerance: float = 0.35,
    angular_tolerance: float = 0.22,
):
    """Return definition-local triangulation and per-corner CAD normals."""

    prepared = _bake_face_location(face)
    BRepTools.Clean_s(prepared, False)
    mesh = BRepMesh_IncrementalMesh(
        prepared,
        float(tolerance),
        False,
        float(angular_tolerance),
        False,
    )
    mesh.Perform()
    loc = TopLoc_Location()
    tri = BRep_Tool.Triangulation_s(prepared, loc, 0)
    if tri is None:
        return [], [], []
    trsf = loc.Transformation()
    vertices = []
    for idx in range(1, tri.NbNodes() + 1):
        p = tri.Node(idx).Transformed(trsf)
        vertices.append((float(p.X()), float(p.Y()), float(p.Z())))
    triangles = []
    corner_normals = []
    reversed_face = face.Orientation() == TopAbs_REVERSED
    for idx in range(1, tri.NbTriangles() + 1):
        a, b, c = tri.Triangle(idx).Get()
        if reversed_face:
            node_indices = (a, c, b)
        else:
            node_indices = (a, b, c)
        triangles.append(tuple(index - 1 for index in node_indices))
        if tri.HasNormals():
            normals = []
            for node_index in node_indices:
                direction = tri.Normal(node_index).Transformed(trsf)
                if reversed_face:
                    direction = direction.Reversed()
                normals.append((float(direction.X()), float(direction.Y()), float(direction.Z())))
            corner_normals.append(tuple(normals))
        else:
            left = vertices[node_indices[1] - 1]
            origin = vertices[node_indices[0] - 1]
            right = vertices[node_indices[2] - 1]
            cross = (
                (left[1] - origin[1]) * (right[2] - origin[2])
                - (left[2] - origin[2]) * (right[1] - origin[1]),
                (left[2] - origin[2]) * (right[0] - origin[0])
                - (left[0] - origin[0]) * (right[2] - origin[2]),
                (left[0] - origin[0]) * (right[1] - origin[1])
                - (left[1] - origin[1]) * (right[0] - origin[0]),
            )
            length = sum(component * component for component in cross) ** 0.5
            normal = tuple(component / length for component in cross) if length > 0.0 else (0.0, 0.0, 0.0)
            corner_normals.append((normal, normal, normal))
    return vertices, triangles, corner_normals


def _bake_face_location(face: TopoDS_Face) -> TopoDS_Face:
    location = face.Location()
    unlocated = face.Located(TopLoc_Location(), False)
    if location.IsIdentity():
        return TopoDS.Face_s(unlocated)
    builder = BRepBuilderAPI_Transform(
        unlocated,
        location.Transformation(),
        True,
        False,
    )
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP face location bake failed")
    return TopoDS.Face_s(builder.Shape())
