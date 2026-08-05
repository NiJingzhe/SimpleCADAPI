"""OCP-native surface construction, filling, lofting, and sewing helpers."""

from __future__ import annotations

from typing import Iterable, Mapping, Sequence

from ocp_gordon import interpolate_curve_network
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_Sewing
from OCP.BRepFill import BRepFill
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeFilling, BRepOffsetAPI_ThruSections
from OCP.Geom import Geom_BSplineCurve, Geom_BezierSurface, Geom_TrimmedCurve
from OCP.GeomAbs import (
    GeomAbs_BSplineCurve,
    GeomAbs_BezierCurve,
    GeomAbs_C0,
    GeomAbs_C2,
    GeomAbs_G1,
    GeomAbs_G2,
)
from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
from OCP.Precision import Precision
from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
from OCP.TColgp import TColgp_Array1OfPnt, TColgp_Array2OfPnt
from OCP.TColStd import (
    TColStd_Array1OfInteger,
    TColStd_Array1OfReal,
    TColStd_Array2OfReal,
)
from OCP.TopAbs import TopAbs_EDGE, TopAbs_FACE, TopAbs_SHELL, TopAbs_VERTEX, TopAbs_WIRE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import (
    TopoDS,
    TopoDS_Edge,
    TopoDS_Face,
    TopoDS_Shape,
    TopoDS_Shell,
    TopoDS_Vertex,
    TopoDS_Wire,
)
from OCP.gp import gp_Pnt

from .ocp_topology import faces_of, wires_of

Point3 = tuple[float, float, float]

_CONTINUITY = {
    "C0": GeomAbs_C0,
    "G1": GeomAbs_G1,
    "G2": GeomAbs_G2,
}


def _point(value: Sequence[float]) -> gp_Pnt:
    return gp_Pnt(float(value[0]), float(value[1]), float(value[2]))


def _point_grid(points: Sequence[Sequence[Sequence[float]]]) -> TColgp_Array2OfPnt:
    rows = len(points)
    columns = len(points[0])
    array = TColgp_Array2OfPnt(1, rows, 1, columns)
    for row_index, row in enumerate(points, start=1):
        for column_index, point in enumerate(row, start=1):
            array.SetValue(row_index, column_index, _point(point))
    return array


def _face_from_surface(surface) -> TopoDS_Face:
    builder = BRepBuilderAPI_MakeFace(surface, Precision.Confusion_s())
    if not builder.IsDone():
        raise ValueError("OCP could not create a face from the generated surface")
    return builder.Face()


def make_bezier_surface(
    control_points: Sequence[Sequence[Sequence[float]]],
    weights: Sequence[Sequence[float]] | None = None,
) -> TopoDS_Face:
    poles = _point_grid(control_points)
    if weights is None:
        surface = Geom_BezierSurface(poles)
    else:
        weight_array = TColStd_Array2OfReal(
            1, len(weights), 1, len(weights[0])
        )
        for row_index, row in enumerate(weights, start=1):
            for column_index, weight in enumerate(row, start=1):
                weight_array.SetValue(row_index, column_index, float(weight))
        surface = Geom_BezierSurface(poles, weight_array)
    return _face_from_surface(surface)


def fit_point_grid_surface(
    points: Sequence[Sequence[Sequence[float]]],
    *,
    tolerance: float,
    degree_min: int,
    degree_max: int,
    smoothing: tuple[float, float, float] | None,
) -> TopoDS_Face:
    point_array = _point_grid(points)
    if smoothing is None:
        builder = GeomAPI_PointsToBSplineSurface(
            point_array,
            DegMin=int(degree_min),
            DegMax=int(degree_max),
            Continuity=GeomAbs_C2,
            Tol3D=float(tolerance),
        )
    else:
        builder = GeomAPI_PointsToBSplineSurface(
            point_array,
            float(smoothing[0]),
            float(smoothing[1]),
            float(smoothing[2]),
            DegMax=int(degree_max),
            Continuity=GeomAbs_C2,
            Tol3D=float(tolerance),
        )
    if not builder.IsDone():
        raise ValueError("OCP B-spline point-grid fitting did not converge")
    return _face_from_surface(builder.Surface())


def make_ruled_face(edge_a: TopoDS_Edge, edge_b: TopoDS_Edge) -> TopoDS_Face:
    face = BRepFill.Face_s(edge_a, edge_b)
    if face.IsNull():
        raise ValueError("OCP ruled-surface construction returned a null face")
    return TopoDS.Face_s(face)


def make_loft_shell(
    sections: Sequence[TopoDS_Wire | TopoDS_Vertex], *, ruled: bool
) -> TopoDS_Shell:
    builder = BRepOffsetAPI_ThruSections(False, bool(ruled))
    builder.CheckCompatibility(True)
    for section in sections:
        if section.ShapeType() == TopAbs_VERTEX:
            builder.AddVertex(TopoDS.Vertex_s(section))
        elif section.ShapeType() == TopAbs_WIRE:
            builder.AddWire(TopoDS.Wire_s(section))
        else:
            raise TypeError("loft sections must contain only vertices or wires")
    builder.Build()
    if not builder.IsDone():
        raise ValueError(f"OCP surface loft failed with status {builder.GetStatus()}")
    shape = builder.Shape()
    if shape.ShapeType() == TopAbs_SHELL:
        return TopoDS.Shell_s(shape)
    shells = _extract(shape, TopAbs_SHELL, TopoDS.Shell_s)
    if len(shells) != 1:
        raise ValueError(
            f"surface loft must create exactly one shell, got {len(shells)}"
        )
    return shells[0]


def _zero_length_bspline(point: gp_Pnt, degree: int = 1) -> Geom_BSplineCurve:
    poles = TColgp_Array1OfPnt(1, 2)
    poles.SetValue(1, point)
    poles.SetValue(2, point)
    knots = TColStd_Array1OfReal(1, 2)
    knots.SetValue(1, 0.0)
    knots.SetValue(2, 1.0)
    multiplicities = TColStd_Array1OfInteger(1, 2)
    multiplicities.SetValue(1, degree + 1)
    multiplicities.SetValue(2, degree + 1)
    return Geom_BSplineCurve(poles, knots, multiplicities, degree)


def _gordon_curve(value: TopoDS_Edge | Sequence[float]):
    if isinstance(value, TopoDS_Edge):
        adaptor = BRepAdaptor_Curve(value)
        curve = BRep_Tool.Curve_s(value, 0.0, 1.0)
        if not (
            (adaptor.IsPeriodic() and adaptor.IsClosed())
            or adaptor.GetType() in {GeomAbs_BSplineCurve, GeomAbs_BezierCurve}
        ):
            curve = Geom_TrimmedCurve(
                curve, adaptor.FirstParameter(), adaptor.LastParameter()
            )
        return curve
    return _zero_length_bspline(_point(value))


def make_gordon_surface(
    profiles: Sequence[TopoDS_Edge | Sequence[float]],
    guides: Sequence[TopoDS_Edge | Sequence[float]],
    *,
    tolerance: float,
) -> TopoDS_Face:
    surface = interpolate_curve_network(
        [_gordon_curve(value) for value in profiles],
        [_gordon_curve(value) for value in guides],
        tolerance=float(tolerance),
    )
    return _face_from_surface(surface)


def make_filling_face(
    boundaries: Sequence[tuple[TopoDS_Edge, TopoDS_Face | None, str]],
    points: Sequence[Sequence[float]],
    *,
    settings: Mapping[str, object],
    holes: Sequence[TopoDS_Wire] = (),
) -> TopoDS_Face:
    builder = BRepOffsetAPI_MakeFilling(
        Degree=int(settings["degree"]),
        NbPtsOnCur=int(settings["points_per_curve"]),
        NbIter=int(settings["iterations"]),
        Anisotropie=bool(settings["anisotropic"]),
        Tol2d=float(settings["tolerance_2d"]),
        Tol3d=float(settings["tolerance_3d"]),
        TolAng=float(settings["angular_tolerance"]),
        TolCurv=float(settings["curvature_tolerance"]),
        MaxDeg=int(settings["max_degree"]),
        MaxSegments=int(settings["max_segments"]),
    )
    for edge, support, continuity in boundaries:
        order = _CONTINUITY[str(continuity)]
        if support is None:
            builder.Add(edge, order)
        else:
            builder.Add(edge, support, order)
    for point in points:
        builder.Add(_point(point))
    builder.Build()
    if not builder.IsDone():
        raise ValueError("OCP constrained surface filling did not converge")
    shape = builder.Shape()
    if shape.ShapeType() != TopAbs_FACE:
        faces = faces_of(shape)
        if len(faces) != 1:
            raise ValueError(
                f"surface filling must create exactly one face, got {len(faces)}"
            )
        face = faces[0]
    else:
        face = TopoDS.Face_s(shape)
    if holes:
        face_builder = BRepBuilderAPI_MakeFace(face)
        for hole in holes:
            face_builder.Add(hole)
        if not face_builder.IsDone():
            raise ValueError("OCP could not trim the filled surface with hole wires")
        face = face_builder.Face()
    return face


def _extract(shape: TopoDS_Shape, kind, caster):
    result = []
    explorer = TopExp_Explorer(shape, kind)
    while explorer.More():
        result.append(caster(explorer.Current()))
        explorer.Next()
    return result


def sew_faces(
    faces: Sequence[TopoDS_Face], *, tolerance: float
) -> TopoDS_Shell:
    sewing = BRepBuilderAPI_Sewing(float(tolerance))
    for face in faces:
        sewing.Add(face)
    sewing.Perform()
    shape = sewing.SewedShape()
    if shape.IsNull():
        raise ValueError("OCP sewing returned a null shape")
    if shape.ShapeType() == TopAbs_SHELL:
        return TopoDS.Shell_s(shape)
    if shape.ShapeType() == TopAbs_FACE:
        return shell_from_face(TopoDS.Face_s(shape))
    shells = _extract(shape, TopAbs_SHELL, TopoDS.Shell_s)
    if len(shells) == 1:
        return shells[0]
    raise ValueError(
        "faces do not sew into exactly one connected shell; "
        f"OCP produced {len(shells)} shell components"
    )


def shell_from_face(face: TopoDS_Face) -> TopoDS_Shell:
    builder = BRep_Builder()
    shell = TopoDS_Shell()
    builder.MakeShell(shell)
    builder.Add(shell, face)
    return shell


def free_boundaries(
    shell: TopoDS_Shell, *, tolerance: float
) -> list[TopoDS_Wire]:
    analysis = ShapeAnalysis_FreeBounds(
        shell, float(tolerance), False, True
    )
    result: list[TopoDS_Wire] = []
    for shape in (analysis.GetClosedWires(), analysis.GetOpenWires()):
        result.extend(wires_of(shape))
    unique: list[TopoDS_Wire] = []
    for wire in result:
        if not any(wire.IsSame(existing) for existing in unique):
            unique.append(wire)
    return unique


def fill_shell_holes(
    shell: TopoDS_Shell,
    *,
    hole_indices: Sequence[int] | None,
    tolerance: float,
    settings: Mapping[str, object],
) -> TopoDS_Shell:
    boundaries = free_boundaries(shell, tolerance=tolerance)
    selected_indices = (
        list(range(len(boundaries)))
        if hole_indices is None
        else [int(index) for index in hole_indices]
    )
    patches: list[TopoDS_Face] = []
    for index in selected_indices:
        wire = boundaries[index]
        if not BRep_Tool.IsClosed_s(wire):
            raise ValueError(
                f"free boundary {index} is open and cannot be filled as a hole"
            )
        edges = _extract(wire, TopAbs_EDGE, TopoDS.Edge_s)
        patches.append(
            make_filling_face(
                [(edge, None, "C0") for edge in edges],
                (),
                settings=settings,
            )
        )
    return sew_faces([*faces_of(shell), *patches], tolerance=tolerance)
