"""OCP-native surface construction, filling, lofting, and sewing helpers."""

from __future__ import annotations

import math
from typing import Iterable, Mapping, Sequence

import numpy as np
from ocp_gordon import interpolate_curve_network
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepClass import BRepClass_FaceClassifier
from OCP.BRepBuilderAPI import (
    BRepBuilderAPI_Copy,
    BRepBuilderAPI_MakeFace,
    BRepBuilderAPI_Sewing,
)
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepTools import BRepTools, BRepTools_WireExplorer
from OCP.BRepFill import BRepFill
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeFilling, BRepOffsetAPI_ThruSections
from OCP.Geom import (
    Geom_BSplineCurve,
    Geom_BezierSurface,
    Geom_CylindricalSurface,
    Geom_TrimmedCurve,
)
from OCP.GeomAbs import (
    GeomAbs_BSplineCurve,
    GeomAbs_BezierCurve,
    GeomAbs_C0,
    GeomAbs_C2,
    GeomAbs_G1,
    GeomAbs_G2,
)
from OCP.GeomAPI import GeomAPI_PointsToBSplineSurface
from OCP.GeomAPI import GeomAPI_ProjectPointOnSurf
from OCP.Precision import Precision
from OCP.ShapeAnalysis import ShapeAnalysis_FreeBounds
from OCP.ShapeFix import ShapeFix_Edge, ShapeFix_Wire
from OCP.TColgp import TColgp_Array1OfPnt, TColgp_Array2OfPnt
from OCP.TColStd import (
    TColStd_Array1OfInteger,
    TColStd_Array1OfReal,
    TColStd_Array2OfReal,
)
from OCP.TopAbs import (
    TopAbs_EDGE,
    TopAbs_FACE,
    TopAbs_IN,
    TopAbs_ON,
    TopAbs_SHELL,
    TopAbs_VERTEX,
    TopAbs_WIRE,
)
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
from OCP.gp import gp_Ax3, gp_Dir, gp_Pnt, gp_Pnt2d

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


def make_cylindrical_surface(
    radius: float,
    u_range: tuple[float, float],
    v_range: tuple[float, float],
    *,
    origin: Sequence[float],
    axis: Sequence[float],
    x_direction: Sequence[float],
    tolerance: float,
) -> TopoDS_Face:
    surface = Geom_CylindricalSurface(
        gp_Ax3(
            _point(origin),
            gp_Dir(float(axis[0]), float(axis[1]), float(axis[2])),
            gp_Dir(
                float(x_direction[0]),
                float(x_direction[1]),
                float(x_direction[2]),
            ),
        ),
        float(radius),
    )
    builder = BRepBuilderAPI_MakeFace(
        surface,
        float(u_range[0]),
        float(u_range[1]),
        float(v_range[0]),
        float(v_range[1]),
        float(tolerance),
    )
    if not builder.IsDone() or builder.Face().IsNull():
        raise ValueError("OCP could not create the bounded cylindrical surface face")
    face = builder.Face()
    if not BRepCheck_Analyzer(face).IsValid():
        raise ValueError("bounded cylindrical surface face is invalid")
    return face


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


def _wire_uv_area(wire: TopoDS_Wire, support: TopoDS_Face) -> float:
    points: list[tuple[float, float]] = []
    explorer = BRepTools_WireExplorer(wire, support)
    while explorer.More():
        edge = TopoDS.Edge_s(explorer.Current())
        first, last = BRep_Tool.Range_s(edge, support)
        pcurve = BRep_Tool.CurveOnSurface_s(edge, support, first, last)
        if pcurve is None:
            raise ValueError("trim wire edge has no pcurve on the carrier")
        parameters = [first + (last - first) * index / 7.0 for index in range(8)]
        if edge.Orientation().name == "TopAbs_REVERSED":
            parameters.reverse()
        for parameter in parameters[:-1]:
            point = pcurve.Value(float(parameter))
            points.append((float(point.X()), float(point.Y())))
        explorer.Next()
    if len(points) < 3:
        raise ValueError("trim wire has fewer than three UV samples")
    return 0.5 * sum(
        first[0] * second[1] - second[0] * first[1]
        for first, second in zip(points, (*points[1:], points[0]))
    )


def _unwrap_periodic(values: Sequence[float], period: float) -> list[float]:
    result = [float(values[0])]
    for value in values[1:]:
        result.append(float(value) + round((result[-1] - float(value)) / period) * period)
    return result


def _fits_parameter_bounds(
    values: Sequence[float],
    lower: float,
    upper: float,
    *,
    tolerance: float,
    period: float | None,
) -> bool:
    checked = list(values)
    if period is None:
        return all(lower - tolerance <= value <= upper + tolerance for value in checked)
    checked = _unwrap_periodic(checked, period)
    if max(checked) - min(checked) > upper - lower + 2.0 * tolerance:
        return False
    minimum_shift = math.ceil((lower - tolerance - min(checked)) / period)
    maximum_shift = math.floor((upper + tolerance - max(checked)) / period)
    return minimum_shift <= maximum_shift


def _validate_trim_wire_domain(
    wire: TopoDS_Wire,
    carrier: TopoDS_Face,
    *,
    tolerance: float,
) -> None:
    surface = BRep_Tool.Surface_s(carrier)
    u_min, u_max, v_min, v_max = (
        float(value) for value in BRepTools.UVBounds_s(carrier)
    )
    u_values: list[float] = []
    v_values: list[float] = []
    explorer = BRepTools_WireExplorer(wire)
    edge_index = 0
    while explorer.More():
        edge = TopoDS.Edge_s(explorer.Current())
        adaptor = BRepAdaptor_Curve(edge)
        first = float(adaptor.FirstParameter())
        last = float(adaptor.LastParameter())
        parameters = np.linspace(first, last, 17).tolist()
        if edge.Orientation().name == "TopAbs_REVERSED":
            parameters.reverse()
        for sample_index, parameter in enumerate(parameters):
            if edge_index and sample_index == 0:
                continue
            projection = GeomAPI_ProjectPointOnSurf(adaptor.Value(parameter), surface)
            if (
                projection.NbPoints() == 0
                or float(projection.LowerDistance()) > float(tolerance)
            ):
                raise ValueError(
                    f"trim edge {edge_index} deviates from the carrier beyond tolerance"
                )
            u_value, v_value = projection.LowerDistanceParameters()
            u_values.append(float(u_value))
            v_values.append(float(v_value))
        edge_index += 1
        explorer.Next()
    if edge_index < 1:
        raise ValueError("trim wire contains no edges")
    u_period = float(surface.UPeriod()) if surface.IsUPeriodic() else None
    v_period = float(surface.VPeriod()) if surface.IsVPeriodic() else None
    u_tolerance = float(tolerance)
    v_tolerance = float(tolerance)
    if isinstance(surface, Geom_CylindricalSurface):
        u_tolerance = float(tolerance) / max(float(surface.Radius()), Precision.Confusion_s())
    if not _fits_parameter_bounds(
        u_values,
        u_min,
        u_max,
        tolerance=u_tolerance,
        period=u_period,
    ) or not _fits_parameter_bounds(
        v_values,
        v_min,
        v_max,
        tolerance=v_tolerance,
        period=v_period,
    ):
        raise ValueError("trim wire lies outside the bounded carrier parameter domain")


def _project_trim_wire(
    wire: TopoDS_Wire, support: TopoDS_Face, *, tolerance: float
) -> TopoDS_Wire:
    surface = BRep_Tool.Surface_s(support)
    source_explorer = BRepTools_WireExplorer(wire)
    source_edge_index = 0
    while source_explorer.More():
        source_edge = TopoDS.Edge_s(source_explorer.Current())
        adaptor = BRepAdaptor_Curve(source_edge)
        first = float(adaptor.FirstParameter())
        last = float(adaptor.LastParameter())
        for sample_index in range(17):
            parameter = first + (last - first) * sample_index / 16.0
            point = adaptor.Value(parameter)
            projection = GeomAPI_ProjectPointOnSurf(point, surface)
            if (
                projection.NbPoints() == 0
                or float(projection.LowerDistance()) > float(tolerance)
            ):
                raise ValueError(
                    f"trim edge {source_edge_index} deviates from the carrier beyond tolerance"
                )
            u_value, v_value = projection.LowerDistanceParameters()
            state = BRepClass_FaceClassifier(
                support,
                gp_Pnt2d(float(u_value), float(v_value)),
                float(tolerance),
            ).State()
            if state not in {TopAbs_IN, TopAbs_ON}:
                raise ValueError(
                    f"trim edge {source_edge_index} lies outside the bounded carrier"
                )
        source_edge_index += 1
        source_explorer.Next()

    copied = BRepBuilderAPI_Copy(wire, True, False)
    copied.Build()
    if not copied.IsDone() or copied.Shape().IsNull():
        raise ValueError("OCP could not copy the trim wire")
    result = TopoDS.Wire_s(copied.Shape())
    edge_fix = ShapeFix_Edge()
    explorer = BRepTools_WireExplorer(result)
    edge_count = 0
    while explorer.More():
        edge = TopoDS.Edge_s(explorer.Current())
        edge_fix.FixAddPCurve(edge, support, False, float(tolerance))
        first, last = BRep_Tool.Range_s(edge)
        if BRep_Tool.CurveOnSurface_s(edge, support, first, last) is None:
            raise ValueError(f"trim edge {edge_count} could not be projected")
        edge_fix.FixSameParameter(edge, support, float(tolerance))
        edge_count += 1
        explorer.Next()
    if edge_count < 1:
        raise ValueError("trim wire contains no edges")
    wire_fix = ShapeFix_Wire(result, support, float(tolerance))
    wire_fix.Perform()
    result = wire_fix.Wire()
    if result.IsNull() or not BRepCheck_Analyzer(result).IsValid():
        raise ValueError("projected trim wire is invalid")
    return result


def trim_surface_face(
    carrier: TopoDS_Face,
    outer: TopoDS_Wire,
    holes: Sequence[TopoDS_Wire],
    *,
    tolerance: float,
) -> TopoDS_Face:
    """Project 3D wires onto a carrier and return one trimmed face."""

    surface = BRep_Tool.Surface_s(carrier)
    if (surface.IsUPeriodic() or surface.IsVPeriodic()) and holes:
        raise ValueError("periodic carrier trimming with holes is not supported")
    _validate_trim_wire_domain(outer, carrier, tolerance=tolerance)
    for wire in holes:
        _validate_trim_wire_domain(wire, carrier, tolerance=tolerance)
    support_builder = BRepBuilderAPI_MakeFace()
    support_builder.Init(surface, False, float(tolerance))
    support = support_builder.Face()
    outer_wire = _project_trim_wire(outer, support, tolerance=tolerance)
    hole_wires = [
        _project_trim_wire(wire, support, tolerance=tolerance) for wire in holes
    ]

    carrier_outer = BRepTools.OuterWire_s(carrier)
    carrier_area = _wire_uv_area(carrier_outer, carrier)
    outer_area = _wire_uv_area(outer_wire, support)
    if carrier_area * outer_area < 0.0:
        outer_wire = TopoDS.Wire_s(outer_wire.Reversed())
        outer_area = -outer_area

    face_builder = BRepBuilderAPI_MakeFace(surface, outer_wire, True)
    for wire in hole_wires:
        area = _wire_uv_area(wire, support)
        face_builder.Add(
            TopoDS.Wire_s(wire.Reversed()) if outer_area * area > 0.0 else wire
        )
    face_builder.Build()
    if not face_builder.IsDone() or face_builder.Face().IsNull():
        raise ValueError("OCP could not build the trimmed surface face")
    face = face_builder.Face()
    if not BRepCheck_Analyzer(face).IsValid():
        raise ValueError("trimmed surface face is invalid")
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
    sewing = BRepBuilderAPI_Sewing(float(tolerance), True, True, False, False)
    sewing.SetNonManifoldMode(False)
    sewing.SetLocalTolerancesMode(False)
    sewing.SetMinTolerance(float(tolerance))
    sewing.SetMaxTolerance(float(tolerance))
    for face in faces:
        sewing.Add(face)
    sewing.Perform()
    if sewing.NbMultipleEdges():
        raise ValueError("face sewing produced non-manifold multiple edges")
    if sewing.NbDeletedFaces():
        raise ValueError("face sewing deleted one or more input faces")
    shape = sewing.SewedShape()
    if shape.IsNull():
        raise ValueError("OCP sewing returned a null shape")
    if shape.ShapeType() == TopAbs_SHELL:
        return TopoDS.Shell_s(shape)
    if shape.ShapeType() == TopAbs_FACE:
        return shell_from_face(TopoDS.Face_s(shape))
    if len(faces_of(shape)) != len(faces):
        raise ValueError("face sewing did not preserve every input face")
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
