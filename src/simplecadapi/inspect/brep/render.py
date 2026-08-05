"""Fast, smooth multi-view rendering for BREP inspection."""

from __future__ import annotations

import colorsys
import math
from pathlib import Path
from typing import Any, Literal, Mapping, Sequence

import numpy as np
from OCP.BRep import BRep_Builder, BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepBuilderAPI import BRepBuilderAPI_Copy
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.TopAbs import (
    TopAbs_EDGE,
    TopAbs_FACE,
    TopAbs_REVERSED,
    TopAbs_SOLID,
    TopAbs_VERTEX,
)
from OCP.TopExp import TopExp, TopExp_Explorer
from OCP.TopTools import TopTools_IndexedMapOfShape
from OCP.TopoDS import TopoDS, TopoDS_Compound, TopoDS_Edge, TopoDS_Shape
from OCP.IFSelect import IFSelect_RetDone
from OCP.Quantity import Quantity_ColorRGBA
from OCP.STEPCAFControl import STEPCAFControl_Reader
from OCP.TCollection import TCollection_ExtendedString
from OCP.TDocStd import TDocStd_Document
from OCP.TopLoc import TopLoc_Location
from OCP.XCAFApp import XCAFApp_Application
from OCP.XCAFDoc import XCAFDoc_DocumentTool, XCAFDoc_ShapeTool
from OCP.XCAFPrs import (
    XCAFPrs,
    XCAFPrs_DocumentExplorer,
    XCAFPrs_DocumentExplorerFlags_OnlyLeafNodes,
    XCAFPrs_IndexedDataMapOfShapeStyle,
)
from OCP.TDF import TDF_LabelSequence
from OCP.TDataStd import TDataStd_Name

from .io import load_step_rshape
from .model import BRepModel, index_shape_rbrepmodel, load_step_rbrepmodel

DEFAULT_VIEWS: tuple[tuple[float, float, str], ...] = (
    (28.0, -45.0, "isometric"),
    (90.0, -90.0, "top / X-Y"),
    (0.0, -90.0, "front / X-Z"),
    (0.0, 0.0, "side / Y-Z"),
)


def _vtk_modules():
    try:
        import vtk
        from vtk.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
    except ImportError as error:
        raise ImportError("BREP rendering requires VTK") from error
    return vtk, numpy_to_vtk, numpy_to_vtkIdTypeArray

_OFFSCREEN_WINDOW: Any | None = None


def _offscreen_window(width: int, height: int):
    """Reuse one native offscreen context across renders.

    VTK's macOS backend can segfault when several windows are finalized in one
    Python process. Renderers are removed before each use; the process owns the
    single native window until exit.
    """
    global _OFFSCREEN_WINDOW
    vtk, _, _ = _vtk_modules()
    if _OFFSCREEN_WINDOW is None:
        _OFFSCREEN_WINDOW = vtk.vtkRenderWindow()
        _OFFSCREEN_WINDOW.SetOffScreenRendering(1)
        _OFFSCREEN_WINDOW.SetMultiSamples(0)
    _OFFSCREEN_WINDOW.GetRenderers().RemoveAllItems()
    _OFFSCREEN_WINDOW.SetSize(width, height)
    return _OFFSCREEN_WINDOW


def _compound(shapes: Sequence[TopoDS_Shape]) -> TopoDS_Shape:
    if len(shapes) == 1:
        return shapes[0]
    builder = BRep_Builder()
    compound = TopoDS_Compound()
    builder.MakeCompound(compound)
    for shape in shapes:
        builder.Add(compound, shape)
    return compound

def _rgba_tuple(color: Quantity_ColorRGBA) -> tuple[float, float, float, float]:
    rgb = color.GetRGB()
    return (float(rgb.Red()), float(rgb.Green()), float(rgb.Blue()), float(color.Alpha()))

def _label_name(label) -> str:
    if label.IsNull():
        return ""
    attribute = TDataStd_Name()
    if label.FindAttribute(TDataStd_Name.GetID_s(), attribute):
        return attribute.Get().ToExtString()
    return ""


def _node_name(node) -> str:
    return _label_name(node.Label) or _label_name(node.RefLabel) or "<unnamed>"

def _path_segment(node) -> str:
    return f"{_node_name(node)}[{node.Id.ToCString()}]"


def _component_records(document: TDocStd_Document) -> list[dict[str, object]]:
    explorer = XCAFPrs_DocumentExplorer(document, 0)
    records: list[dict[str, object]] = []
    while explorer.More():
        node = explorer.Current()
        name = _node_name(node)
        records.append(
            {
                "name": name,
                "path": tuple(
                    _path_segment(explorer.Current(depth))
                    for depth in range(explorer.CurrentDepth() + 1)
                ),
                "node_id": node.Id.ToCString(),
                "depth": int(explorer.CurrentDepth()),
                "assembly": bool(node.IsAssembly),
                "shape": XCAFDoc_ShapeTool.GetShape_s(node.RefLabel).Moved(
                    node.Location,
                    False,
                ),
            }
        )
        explorer.Next()
    return records


def _load_step_xcaf_document(
    path: str | Path,
) -> tuple[TDocStd_Document, TopoDS_Shape, dict[int, tuple[float, float, float, float]]]:
    """Load one styled STEP/XCAF document and its effective face colors."""
    application = XCAFApp_Application.GetApplication_s()
    del application
    document = TDocStd_Document(TCollection_ExtendedString("BinXCAF"))
    reader = STEPCAFControl_Reader()
    reader.SetColorMode(True)
    reader.SetNameMode(True)
    status = reader.ReadFile(str(path))
    if status != IFSelect_RetDone or not reader.Transfer(document):
        raise ValueError(f"Could not read styled STEP file {path}: {status}")

    shape_tool = XCAFDoc_DocumentTool.ShapeTool_s(document.Main())
    roots = TDF_LabelSequence()
    shape_tool.GetFreeShapes(roots)
    if roots.Length() < 1:
        raise ValueError(f"STEP file {path} contains no free shapes")
    root = shape_tool.GetOneShape()
    face_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(root, TopAbs_FACE, face_map)
    face_colors: dict[int, tuple[float, float, float, float]] = {}

    explorer = XCAFPrs_DocumentExplorer(
        document,
        XCAFPrs_DocumentExplorerFlags_OnlyLeafNodes,
    )
    while explorer.More():
        node = explorer.Current()
        style = node.Style
        if style.IsVisible() and style.IsSetColorSurf():
            shape = XCAFDoc_ShapeTool.GetShape_s(node.RefLabel).Moved(
                node.Location,
                False,
            )
            faces = TopTools_IndexedMapOfShape()
            TopExp.MapShapes_s(shape, TopAbs_FACE, faces)
            color = _rgba_tuple(style.GetColorSurfRGBA())
            for index in range(1, faces.Extent() + 1):
                root_index = face_map.FindIndex(faces.FindKey(index))
                if root_index > 0:
                    face_colors[root_index] = color
        explorer.Next()

    settings = XCAFPrs_IndexedDataMapOfShapeStyle()
    for index in range(1, roots.Length() + 1):
        XCAFPrs.CollectStyleSettings_s(
            roots.Value(index),
            TopLoc_Location(),
            settings,
        )
    for index in range(1, settings.Extent() + 1):
        shape = settings.FindKey(index)
        style = settings.FindFromIndex(index)
        if (
            shape.ShapeType() == TopAbs_FACE
            and style.IsVisible()
            and style.IsSetColorSurf()
        ):
            root_index = face_map.FindIndex(shape)
            if root_index > 0:
                face_colors[root_index] = _rgba_tuple(style.GetColorSurfRGBA())
    return document, root, face_colors
def _load_step_xcaf(
    path: str | Path,
) -> tuple[TopoDS_Shape, dict[int, tuple[float, float, float, float]]]:
    """Load STEP geometry and effective per-face XCAF presentation colors."""
    _, root, face_colors = _load_step_xcaf_document(path)
    return root, face_colors


def _mesh_polydata(
    shapes: Sequence[TopoDS_Shape],
    linear_deflection: float,
    angular_deflection: float,
    face_colors: Mapping[int, tuple[float, float, float, float]] | None = None,
):
    """Tessellate BREP faces into one GPU-friendly VTK dataset.

    OpenCascade supplies per-face vertex normals. Face-local vertices remain
    separate, which keeps sharp BREP boundaries sharp while smoothing adjacent
    triangles on the same analytic face.
    """
    if not shapes:
        return None
    if linear_deflection <= 0.0 or angular_deflection <= 0.0:
        raise ValueError("mesh deflections must be greater than zero")

    copy = BRepBuilderAPI_Copy(_compound(shapes), True, False)
    render_shape = copy.Shape()
    BRepMesh_IncrementalMesh(
        render_shape,
        linear_deflection,
        False,
        angular_deflection,
        True,
    )

    point_blocks: list[np.ndarray] = []
    normal_blocks: list[np.ndarray] = []
    triangle_blocks: list[np.ndarray] = []
    point_offset = 0
    color_blocks: list[np.ndarray] = []
    source_face_index = 0
    explorer = TopExp_Explorer(render_shape, TopAbs_FACE)
    while explorer.More():
        source_face_index += 1
        face = TopoDS.Face_s(explorer.Current())
        location = face.Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is None or triangulation.NbTriangles() == 0:
            explorer.Next()
            continue
        if not triangulation.HasNormals():
            triangulation.ComputeNormals()

        transform = location.Transformation()
        reversed_face = face.Orientation() == TopAbs_REVERSED
        points = np.empty((triangulation.NbNodes(), 3), dtype=np.float32)
        normals = np.empty_like(points)
        for node_index in range(1, triangulation.NbNodes() + 1):
            point = triangulation.Node(node_index)
            point.Transform(transform)
            points[node_index - 1] = point.Coord()
            normal = triangulation.Normal(node_index)
            normal.Transform(transform)
            normals[node_index - 1] = normal.Coord()
        if reversed_face:
            normals *= -1.0

        triangles = np.empty(
            (triangulation.NbTriangles(), 3),
            dtype=np.int64,
        )
        for triangle_index in range(1, triangulation.NbTriangles() + 1):
            triangle = triangulation.Triangle(triangle_index)
            indices = [
                triangle.Value(1) - 1,
                triangle.Value(2) - 1,
                triangle.Value(3) - 1,
            ]
            if reversed_face:
                indices[1], indices[2] = indices[2], indices[1]
            triangles[triangle_index - 1] = np.asarray(indices) + point_offset
        if face_colors is not None:
            rgba = face_colors.get(source_face_index, (0.55, 0.64, 0.73, 1.0))
            color = np.asarray(
                [round(255.0 * component) for component in rgba],
                dtype=np.uint8,
            )
            color_blocks.append(
                np.repeat(color[None, :], len(triangles), axis=0)
            )

        point_blocks.append(points)
        normal_blocks.append(normals)
        triangle_blocks.append(triangles)
        point_offset += len(points)
        explorer.Next()

    if not point_blocks:
        raise ValueError("OpenCascade produced no renderable triangles")

    points = np.concatenate(point_blocks)
    normals = np.concatenate(normal_blocks)
    triangles = np.concatenate(triangle_blocks)
    colors = np.concatenate(color_blocks) if color_blocks else None
    vtk, numpy_to_vtk, numpy_to_vtk_id = _vtk_modules()
    polydata = vtk.vtkPolyData()
    vtk_points = vtk.vtkPoints()
    vtk_points.SetData(numpy_to_vtk(points, deep=False))
    polydata.SetPoints(vtk_points)

    offsets = np.arange(0, 3 * (len(triangles) + 1), 3, dtype=np.int64)
    cells = vtk.vtkCellArray()
    cells.SetData(
        numpy_to_vtk_id(offsets, deep=False),
        numpy_to_vtk_id(triangles.reshape(-1), deep=False),
    )
    polydata.SetPolys(cells)
    vtk_normals = numpy_to_vtk(normals, deep=False)
    vtk_normals.SetName("Normals")
    polydata.GetPointData().SetNormals(vtk_normals)
    if colors is not None:
        vtk_colors = numpy_to_vtk(colors, deep=False)
        vtk_colors.SetName("STEP_RGBA")
        polydata.GetCellData().SetScalars(vtk_colors)
    polydata._simplecad_numpy_refs = (points, normals, triangles, offsets, colors)
    return polydata


def _sample_edge(
    edge: TopoDS_Edge,
    *,
    deflection: float | None = None,
    sample_count: int | None = None,
) -> np.ndarray:
    if BRep_Tool.Degenerated_s(edge):
        return np.empty((0, 3), dtype=np.float32)
    adaptor = BRepAdaptor_Curve(edge)
    first = float(adaptor.FirstParameter())
    last = float(adaptor.LastParameter())
    parameters: list[float]
    if sample_count is not None:
        parameters = np.linspace(first, last, sample_count).tolist()
    else:
        sampler = GCPnts_QuasiUniformDeflection(adaptor, float(deflection))
        if sampler.IsDone() and sampler.NbPoints() >= 2:
            return np.asarray(
                [sampler.Value(index).Coord() for index in range(1, sampler.NbPoints() + 1)],
                dtype=np.float32,
            )
        parameters = [first, last]
    return np.asarray(
        [adaptor.Value(float(parameter)).Coord() for parameter in parameters],
        dtype=np.float32,
    )


def _edge_polydata(
    shapes: Sequence[TopoDS_Shape],
    *,
    deflection: float | None = None,
    sample_count: int | None = None,
):
    if not shapes:
        return None
    if deflection is not None and deflection <= 0.0:
        raise ValueError("edge deflection must be greater than zero")
    if sample_count is not None and sample_count < 2:
        raise ValueError("edge sample count must be at least two")

    edge_map = TopTools_IndexedMapOfShape()
    TopExp.MapShapes_s(_compound(shapes), TopAbs_EDGE, edge_map)
    point_blocks: list[np.ndarray] = []
    cell_blocks: list[np.ndarray] = []
    point_offset = 0
    for index in range(1, edge_map.Extent() + 1):
        points = _sample_edge(
            TopoDS.Edge_s(edge_map.FindKey(index)),
            deflection=deflection,
            sample_count=sample_count,
        )
        if len(points) < 2:
            continue
        point_blocks.append(points)
        cell_blocks.append(np.arange(point_offset, point_offset + len(points), dtype=np.int64))
        point_offset += len(points)
    if not point_blocks:
        return None

    points = np.concatenate(point_blocks)
    offsets = np.empty(len(cell_blocks) + 1, dtype=np.int64)
    offsets[0] = 0
    offsets[1:] = np.cumsum([len(cell) for cell in cell_blocks])
    connectivity = np.concatenate(cell_blocks)
    vtk, numpy_to_vtk, numpy_to_vtk_id = _vtk_modules()
    polydata = vtk.vtkPolyData()
    vtk_points = vtk.vtkPoints()
    vtk_points.SetData(numpy_to_vtk(points, deep=False))
    polydata.SetPoints(vtk_points)
    lines = vtk.vtkCellArray()
    lines.SetData(
        numpy_to_vtk_id(offsets, deep=False),
        numpy_to_vtk_id(connectivity, deep=False),
    )
    polydata._simplecad_numpy_refs = (points, offsets, connectivity)
    polydata.SetLines(lines)
    return polydata



def _hex_rgb(value: str) -> tuple[float, float, float]:
    token = value.removeprefix("#")
    return tuple(int(token[index : index + 2], 16) / 255.0 for index in (0, 2, 4))


def _screenshot_view_angles(
    view: str | Sequence[float],
    spans: Sequence[float],
) -> tuple[float, float]:
    if isinstance(view, str):
        token = view.strip().lower()
        if token == "auto":
            return (22.0 if spans[2] <= max(spans[0], spans[1]) else 35.0, 35.0 if spans[0] >= spans[1] else 125.0)
        presets = {
            "iso": (25.0, 35.0),
            "isometric": (25.0, 35.0),
            "top": (90.0, 0.0),
            "bottom": (-90.0, 0.0),
            "front": (0.0, -90.0),
            "back": (0.0, 90.0),
            "left": (0.0, 180.0),
            "right": (0.0, 0.0),
            "front_right": (20.0, -45.0),
            "front_left": (20.0, 135.0),
            "rear_right": (20.0, 45.0),
            "rear_left": (20.0, -135.0),
        }
        if token not in presets:
            raise ValueError(f"Unsupported view preset: {view}")
        return presets[token]
    if len(view) != 2:
        raise ValueError("view must be an (elevation, azimuth) pair")
    return float(view[0]), float(view[1])


def _render_sdk_screenshot_rpath(
    solids: Sequence[Any],
    output_path: str | Path,
    *,
    highlight_tags: Sequence[str] = (),
    tag_labels: Mapping[str, str] | None = None,
    image_size: tuple[int, int] = (1400, 900),
    view: str | Sequence[float] = "auto",
    show_axes: bool = True,
    show_legend: bool = True,
    zoom: float = 4.0,
    show_callouts: bool = True,
    linear_deflection: float = 0.35,
    angular_deflection: float = 0.22,
) -> Path:
    """Render SDK Solid tags through the shared OCCT/VTK pipeline."""
    if not solids:
        raise ValueError("At least one Solid is required")
    if image_size[0] < 1 or image_size[1] < 1:
        raise ValueError("image_size values must be greater than zero")
    if zoom <= 0.0:
        raise ValueError("zoom must be greater than zero")

    tags = tuple(str(tag) for tag in highlight_tags)
    labels = dict(tag_labels or {})
    palette = (
        "#f39c12",
        "#9b59b6",
        "#f1c40f",
        "#1abc9c",
        "#e67e22",
        "#e84393",
        "#16a085",
        "#d35400",
    )
    tag_colors = {
        tag: _hex_rgb(palette[index % len(palette)])
        for index, tag in enumerate(tags)
    }
    grouped_faces: dict[str | None, list[TopoDS_Shape]] = {None: []}
    label_points: dict[str, tuple[float, float, float]] = {}
    shapes: list[TopoDS_Shape] = []
    for solid in solids:
        shapes.append(solid.wrapped)
        solid_tag = next((tag for tag in tags if solid._has_tag(tag)), None)
        if solid_tag is not None and solid_tag not in label_points:
            box = _mesh_polydata([solid.wrapped], linear_deflection, angular_deflection).GetBounds()
            label_points[solid_tag] = (
                (box[0] + box[1]) * 0.5,
                (box[2] + box[3]) * 0.5,
                (box[4] + box[5]) * 0.5,
            )
        for face in solid.get_faces():
            face_tag = next((tag for tag in tags if face._has_tag(tag)), None)
            selected_tag = face_tag or solid_tag
            grouped_faces.setdefault(selected_tag, []).append(face.wrapped)
            if face_tag is not None and face_tag not in label_points:
                center = face.get_center()
                label_points[face_tag] = (center.x, center.y, center.z)

    vtk, _, _ = _vtk_modules()
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.067, 0.067, 0.067)
    renderer.SetUseFXAA(True)
    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(int(image_size[0]), int(image_size[1]))
    window.SetMultiSamples(4)
    window.AddRenderer(renderer)

    base_faces = grouped_faces.pop(None, [])
    if base_faces:
        renderer.AddActor(
            _surface_actor(
                _mesh_polydata(base_faces, linear_deflection, angular_deflection),
                (0.6, 0.62, 0.64),
                1.0,
            )
        )
    for tag, faces in grouped_faces.items():
        if not faces:
            continue
        renderer.AddActor(
            _surface_actor(
                _mesh_polydata(faces, linear_deflection, angular_deflection),
                tag_colors[str(tag)],
                1.0,
            )
        )
    edges = _edge_polydata(shapes, deflection=linear_deflection)
    if edges is not None:
        renderer.AddActor(_line_actor(edges, (0.78, 0.80, 0.84), 1.0))

    bounds = renderer.ComputeVisiblePropBounds()
    spans = (bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4])
    elevation, azimuth = _screenshot_view_angles(view, spans)
    _set_camera(renderer, elevation, azimuth)
    renderer.GetActiveCamera().Zoom(zoom / 4.0)
    renderer.ResetCameraClippingRange()

    if show_axes:
        axis_length = max(max(spans) * 0.3, 1.0)
        axes = vtk.vtkAxesActor()
        axes.SetTotalLength(axis_length, axis_length, axis_length)
        axes.SetShaftTypeToCylinder()
        renderer.AddActor(axes)
        renderer.ResetCameraClippingRange()

    if show_legend and (tags or show_axes):
        legend_items = [(tag, labels.get(tag, tag), tag_colors[tag]) for tag in tags]
        if show_axes:
            legend_items.extend(
                (
                    ("axis.x", "+X", (1.0, 0.35, 0.35)),
                    ("axis.y", "+Y", (0.35, 1.0, 0.55)),
                    ("axis.z", "+Z", (0.45, 0.65, 1.0)),
                )
            )
        for index, (_, label, color) in enumerate(legend_items):
            actor = vtk.vtkTextActor()
            actor.SetInput(f"■ {label}")
            actor.SetPosition(18, image_size[1] - 28 - index * 24)
            prop = actor.GetTextProperty()
            prop.SetColor(*color)
            prop.SetFontSize(16)
            prop.SetBold(True)
            renderer.AddViewProp(actor)

    if show_callouts:
        for tag, point in label_points.items():
            callout = vtk.vtkBillboardTextActor3D()
            callout.SetInput(labels.get(tag, tag))
            callout.SetPosition(*point)
            prop = callout.GetTextProperty()
            prop.SetColor(1.0, 0.82, 0.48)
            prop.SetBackgroundColor(0.067, 0.067, 0.067)
            prop.SetBackgroundOpacity(0.9)
            prop.SetFontSize(18)
            renderer.AddViewProp(callout)

    window.Render()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_window(window, output)
    window.Finalize()
    return output
def _point_polydata(points: Sequence[Sequence[float]]):
    if not points:
        return None
    vtk, numpy_to_vtk, numpy_to_vtk_id = _vtk_modules()
    values = np.asarray(points, dtype=np.float32)
    polydata = vtk.vtkPolyData()
    vtk_points = vtk.vtkPoints()
    vtk_points.SetData(numpy_to_vtk(values, deep=False))
    polydata.SetPoints(vtk_points)
    offsets = np.arange(len(values) + 1, dtype=np.int64)
    vertices = vtk.vtkCellArray()
    vertices.SetData(
        numpy_to_vtk_id(offsets, deep=False),
        numpy_to_vtk_id(np.arange(len(values), dtype=np.int64), deep=False),
    )
    polydata.SetVerts(vertices)
    polydata._simplecad_numpy_refs = (values, offsets)
    return polydata


def _surface_actor(polydata, color: tuple[float, float, float], opacity: float):
    vtk, _, _ = _vtk_modules()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(polydata)
    if polydata.GetCellData().GetScalars() is not None:
        mapper.SetScalarModeToUseCellData()
        mapper.SetColorModeToDirectScalars()
        mapper.ScalarVisibilityOn()
    else:
        mapper.ScalarVisibilityOff()
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    prop = actor.GetProperty()
    prop.SetColor(*color)
    prop.SetOpacity(opacity)
    prop.SetInterpolationToPhong()
    prop.SetAmbient(0.24)
    prop.SetDiffuse(0.72)
    prop.SetSpecular(0.22)
    prop.SetSpecularPower(28.0)
    prop.EdgeVisibilityOff()
    return actor


def _line_actor(polydata, color: tuple[float, float, float], width: float):
    vtk, _, _ = _vtk_modules()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(polydata)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    actor.GetProperty().SetLineWidth(width)
    actor.GetProperty().LightingOff()
    return actor


def _point_actor(polydata, color: tuple[float, float, float], size: float):
    vtk, _, _ = _vtk_modules()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputData(polydata)
    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().SetColor(*color)
    actor.GetProperty().SetPointSize(size)
    actor.GetProperty().LightingOff()
    return actor


def _add_geometry_callouts(
    renderer,
    callouts: Sequence[
        tuple[str, tuple[float, float, float], tuple[float, float, float]]
    ],
    *,
    font_size: int,
    viewport_size: tuple[int, int],
) -> list[tuple[Any, ...]]:
    """Project anchors to non-overlapping 2D labels connected by leader lines."""
    vtk, _, _ = _vtk_modules()
    width, height = viewport_size
    margin = 12
    line_height = font_size + 8
    placed: list[tuple[float, float, float, float]] = []
    resources: list[tuple[Any, ...]] = []

    def overlaps(box: tuple[float, float, float, float]) -> bool:
        return any(
            box[0] < other[2]
            and box[2] > other[0]
            and box[1] < other[3]
            and box[3] > other[1]
            for other in placed
        )

    origin_x, origin_y = renderer.GetOrigin()
    for index, (label, anchor, color) in enumerate(callouts):
        renderer.SetWorldPoint(*anchor, 1.0)
        renderer.WorldToDisplay()
        display_x, display_y, _ = renderer.GetDisplayPoint()
        anchor_x = display_x - origin_x
        anchor_y = display_y - origin_y
        label_width = max(88, int(len(label) * font_size * 0.62) + 12)
        offset_x = 18 if index % 2 == 0 else -label_width - 18
        offset_y = 14 if index % 4 < 2 else -line_height - 14
        label_x = min(max(anchor_x + offset_x, margin), width - label_width - margin)
        label_y = min(max(anchor_y + offset_y, margin), height - line_height - margin)
        attempts = 0
        box = (label_x, label_y, label_x + label_width, label_y + line_height)
        while overlaps(box) and attempts < 24:
            label_y += line_height if attempts % 2 == 0 else -2 * line_height
            label_y = min(max(label_y, margin), height - line_height - margin)
            if attempts % 4 == 3:
                label_x = min(
                    max(label_x + label_width + 16, margin),
                    width - label_width - margin,
                )
            box = (label_x, label_y, label_x + label_width, label_y + line_height)
            attempts += 1
        placed.append(box)
        line_end_x = label_x if label_x >= anchor_x else label_x + label_width
        line_end_y = label_y + line_height * 0.5
        points = vtk.vtkPoints()
        points.InsertNextPoint(anchor_x, anchor_y, 0.0)
        points.InsertNextPoint(line_end_x, line_end_y, 0.0)
        lines = vtk.vtkCellArray()
        lines.InsertNextCell(2)
        lines.InsertCellPoint(0)
        lines.InsertCellPoint(1)
        polydata = vtk.vtkPolyData()
        polydata.SetPoints(points)
        polydata.SetLines(lines)
        mapper = vtk.vtkPolyDataMapper2D()
        mapper.SetInputData(polydata)
        leader = vtk.vtkActor2D()
        leader.SetMapper(mapper)
        leader.GetProperty().SetColor(*color)
        leader.GetProperty().SetLineWidth(2.0)
        renderer.AddViewProp(leader)
        resources.append((points, lines, polydata, mapper, leader))
        actor = vtk.vtkTextActor()
        actor.SetInput(label)
        actor.SetPosition(label_x, label_y)
        prop = actor.GetTextProperty()
        prop.SetColor(*color)
        prop.SetBackgroundColor(0.04, 0.05, 0.07)
        prop.SetBackgroundOpacity(0.86)
        prop.SetFontSize(font_size)
        prop.SetBold(True)
        renderer.AddViewProp(actor)
        resources.append((actor,))
    return resources


def _set_camera(renderer, elevation: float, azimuth: float) -> None:
    bounds = renderer.ComputeVisiblePropBounds()
    center = np.asarray(
        [
            (bounds[0] + bounds[1]) * 0.5,
            (bounds[2] + bounds[3]) * 0.5,
            (bounds[4] + bounds[5]) * 0.5,
        ]
    )
    spans = np.asarray(
        [bounds[1] - bounds[0], bounds[3] - bounds[2], bounds[5] - bounds[4]]
    )
    elevation_radians = math.radians(elevation)
    azimuth_radians = math.radians(azimuth)
    direction = np.asarray(
        [
            math.cos(elevation_radians) * math.cos(azimuth_radians),
            math.cos(elevation_radians) * math.sin(azimuth_radians),
            math.sin(elevation_radians),
        ]
    )
    distance = max(float(np.linalg.norm(spans)) * 2.5, 1.0)
    camera = renderer.GetActiveCamera()
    camera.ParallelProjectionOn()
    camera.SetFocalPoint(*center)
    camera.SetPosition(*(center + direction * distance))
    if abs(direction[2]) > 0.95:
        camera.SetViewUp(0.0, 1.0, 0.0)
    else:
        camera.SetViewUp(0.0, 0.0, 1.0)
    renderer.ResetCamera()
    camera.Zoom(0.92)
    renderer.ResetCameraClippingRange()


def _write_window(window, output: Path) -> None:
    vtk, _, _ = _vtk_modules()
    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.ReadFrontBufferOff()
    capture.Update()
    suffix = output.suffix.lower()
    writers = {
        ".png": vtk.vtkPNGWriter,
        ".jpg": vtk.vtkJPEGWriter,
        ".jpeg": vtk.vtkJPEGWriter,
        ".tif": vtk.vtkTIFFWriter,
        ".tiff": vtk.vtkTIFFWriter,
    }
    if suffix not in writers:
        raise ValueError("render output must be PNG, JPEG, or TIFF")
    writer = writers[suffix]()
    writer.SetFileName(str(output))
    writer.SetInputConnection(capture.GetOutputPort())
    writer.Write()


def _render_polydata_views(
    base_polydata,
    output_path: str | Path,
    *,
    title: str,
    views: Sequence[tuple[float, float, str]],
    image_size: tuple[float, float],
    dpi: int,
    context_opacity: float = 1.0,
    highlight_edge_width: float = 4.5,
    highlight_point_size: float = 15.0,
    brep_edge_polydata=None,
    highlighted_polydata=None,
    highlighted_edge_polydata=None,
    highlighted_point_polydata=None,
    highlighted_groups=None,
    highlighted_edge_groups=None,
    highlighted_point_groups=None,
    legend: Sequence[tuple[str, tuple[float, float, float]]] | None = None,
    legend_columns: int = 1,
    legend_panel: bool = False,
    callouts: Sequence[
        tuple[str, tuple[float, float, float], tuple[float, float, float]]
    ]
    | None = None,
) -> Path:
    """Render smooth views; optionally multiple colored highlight groups.

    ``highlighted_groups`` is a sequence of ``(polydata, rgb, opacity)``
    triples rendered as separate colored actors; ``highlighted_edge_groups``
    and ``highlighted_point_groups`` are ``(polydata, rgb)`` pairs. ``legend``
    is a list of ``(label, rgb)`` entries drawn in the first viewport.
    ``callouts`` is ``(label, anchor, rgb)`` entries drawn next to their
    geometry with same-color anchor markers in every viewport.
    """
    if not views:
        raise ValueError("at least one render view is required")
    if dpi < 1 or image_size[0] <= 0.0 or image_size[1] <= 0.0:
        raise ValueError("image size and DPI must be greater than zero")
    if highlight_edge_width <= 0.0:
        raise ValueError("highlight_edge_width must be greater than zero")
    if highlight_point_size <= 0.0:
        raise ValueError("highlight_point_size must be greater than zero")
    if legend_columns < 1:
        raise ValueError("legend_columns must be at least one")
    vtk, _, _ = _vtk_modules()
    width = max(1, int(round(image_size[0] * dpi)))
    height = max(1, int(round(image_size[1] * dpi)))
    legend_panel_width = int(width * 0.30) if legend and legend_panel else 0
    render_width = width - legend_panel_width
    columns = min(2, len(views))
    rows = (len(views) + columns - 1) // columns
    window = _offscreen_window(width, height)
    callout_resources: list[tuple[Any, ...]] = []
    callout_renderers: list[tuple[Any, int]] = []

    for index, (elevation, azimuth, view_title) in enumerate(views):
        row = index // columns
        column = index % columns
        left = column / columns * render_width / width
        right = (column + 1) / columns * render_width / width
        top = 1.0 - row / rows
        bottom = 1.0 - (row + 1) / rows
        renderer = vtk.vtkRenderer()
        renderer.SetViewport(left, bottom, right, top)
        renderer.GradientBackgroundOn()
        renderer.SetBackground(0.94, 0.96, 0.98)
        renderer.SetBackground2(0.78, 0.84, 0.90)
        renderer.SetUseFXAA(True)
        if context_opacity < 1.0:
            renderer.SetUseDepthPeeling(True)
            renderer.SetMaximumNumberOfPeels(24)
            renderer.SetOcclusionRatio(0.05)
        if base_polydata is not None:
            renderer.AddActor(_surface_actor(base_polydata, (0.55, 0.64, 0.73), context_opacity))
        if brep_edge_polydata is not None:
            renderer.AddActor(_line_actor(brep_edge_polydata, (0.16, 0.21, 0.27), 1.0))
        if highlighted_groups:
            for polydata, color, opacity in highlighted_groups:
                renderer.AddActor(_surface_actor(polydata, color, opacity))
        elif highlighted_polydata is not None:
            renderer.AddActor(_surface_actor(highlighted_polydata, (0.94, 0.18, 0.30), 1.0))
        if highlighted_edge_groups:
            for polydata, color in highlighted_edge_groups:
                renderer.AddActor(_line_actor(polydata, color, highlight_edge_width))
        elif highlighted_edge_polydata is not None:
            renderer.AddActor(
                _line_actor(highlighted_edge_polydata, (0.78, 0.0, 0.0), highlight_edge_width)
            )
        if highlighted_point_groups:
            for polydata, color in highlighted_point_groups:
                renderer.AddActor(_point_actor(polydata, color, highlight_point_size))
        elif highlighted_point_polydata is not None:
            renderer.AddActor(
                _point_actor(highlighted_point_polydata, (0.78, 0.0, 0.0), highlight_point_size)
            )
        label = vtk.vtkTextActor()
        label.SetInput(f"{title}\n{view_title}" if index == 0 else view_title)
        label.SetPosition(16, 14)
        text = label.GetTextProperty()
        text.SetColor(0.08, 0.11, 0.15)
        text.SetFontSize(max(14, min(width // columns, height // rows) // 34))
        text.SetBold(True)
        renderer.AddViewProp(label)
        if index == 0 and legend and not legend_panel:
            viewport_width = render_width // columns
            viewport_height = height // rows
            legend_font = max(10, min(16, min(viewport_width, viewport_height) // 52))
            legend_spacing = int(legend_font * 1.55)
            legend_rows = (len(legend) + legend_columns - 1) // legend_columns
            column_width = max(
                112,
                max(int(len(entry_label) * legend_font * 0.62) + 26 for entry_label, _ in legend),
            )
            start_x = max(16, viewport_width - column_width * legend_columns - 16)
            start_y = max(48, viewport_height - legend_spacing * legend_rows - 18)
            for legend_index, (entry_label, entry_rgb) in enumerate(legend):
                column = legend_index // legend_rows
                legend_row = legend_index % legend_rows
                entry = vtk.vtkTextActor()
                entry.SetInput(f"■ {entry_label}")
                entry.SetPosition(
                    start_x + column * column_width,
                    start_y + (legend_rows - legend_row - 1) * legend_spacing,
                )
                entry_prop = entry.GetTextProperty()
                entry_prop.SetColor(float(entry_rgb[0]), float(entry_rgb[1]), float(entry_rgb[2]))
                entry_prop.SetBackgroundColor(0.94, 0.96, 0.98)
                entry_prop.SetBackgroundOpacity(0.82)
                entry_prop.SetFontSize(legend_font)
                entry_prop.SetBold(True)
                renderer.AddViewProp(entry)
        window.AddRenderer(renderer)
        _set_camera(renderer, elevation, azimuth)
        if callouts:
            callout_renderers.append((renderer, index))
    if legend and legend_panel:
        panel = vtk.vtkRenderer()
        panel.SetViewport(render_width / width, 0.0, 1.0, 1.0)
        panel.SetBackground(0.94, 0.96, 0.98)
        panel.SetInteractive(False)
        panel_font = max(10, min(16, height // 78))
        panel_spacing = int(panel_font * 1.55)
        panel_rows = (len(legend) + legend_columns - 1) // legend_columns
        panel_column_width = legend_panel_width / legend_columns
        start_y = height - panel_spacing * 2
        for legend_index, (entry_label, entry_rgb) in enumerate(legend):
            column = legend_index // panel_rows
            legend_row = legend_index % panel_rows
            entry = vtk.vtkTextActor()
            entry.SetInput(f"■ {entry_label}")
            entry.SetPosition(
                12 + column * panel_column_width,
                start_y - legend_row * panel_spacing,
            )
            entry_prop = entry.GetTextProperty()
            entry_prop.SetColor(float(entry_rgb[0]), float(entry_rgb[1]), float(entry_rgb[2]))
            entry_prop.SetFontSize(panel_font)
            entry_prop.SetBold(True)
            panel.AddViewProp(entry)
        window.AddRenderer(panel)

    window.Render()
    for renderer, index in callout_renderers:
        callout_resources.extend(
            _add_geometry_callouts(
                renderer,
                callouts or (),
                font_size=max(
                    12,
                    min(18, min(width // columns, height // rows) // 48),
                ),
                viewport_size=(width // columns, height // rows),
            )
        )
    if callout_renderers:
        window.Render()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    _write_window(window, output)
    return output
def render_shape_views_rpath(
    shape: TopoDS_Shape,
    output_path: str | Path,
    *,
    title: str = "BREP views",
    views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS,
    image_size: tuple[float, float] = (18.0, 12.0),
    dpi: int = 180,
    linear_deflection: float = 0.12,
    angular_deflection: float = 0.18,
    show_brep_edges: bool = True,
) -> Path:
    """Render smooth shaded BREP views with true topology edges by default.

    ``show_brep_edges`` draws exact topological edges sampled from the BREP; it
    never exposes the internal triangle edges used by the GPU.
    """
    base = _mesh_polydata([shape], linear_deflection, angular_deflection)
    edges = (
        _edge_polydata([shape], deflection=linear_deflection)
        if show_brep_edges
        else None
    )
    return _render_polydata_views(
        base,
        output_path,
        title=title,
        views=views,
        image_size=image_size,
        dpi=dpi,
        brep_edge_polydata=edges,
    )


def inspect_step_components_rdescriptorlist(step_path: str | Path) -> list[dict[str, object]]:
    """List targetable XCAF component occurrences with unique hierarchy paths."""
    document, _, _ = _load_step_xcaf_document(step_path)
    result: list[dict[str, object]] = []
    for record in _component_records(document):
        shape = record["shape"]
        solid_map = TopTools_IndexedMapOfShape()
        TopExp.MapShapes_s(shape, TopAbs_SOLID, solid_map)
        result.append(
            {
                "name": record["name"],
                "path": "/".join(record["path"]),
                "node_id": record["node_id"],
                "depth": record["depth"],
                "assembly": record["assembly"],
                "solid_count": solid_map.Extent(),
            }
        )
    return result


def _resolve_step_components(
    document: TDocStd_Document,
    selectors: Sequence[str],
) -> list[dict[str, object]]:
    if not selectors:
        raise ValueError("At least one component name or path is required")
    records = _component_records(document)
    selected: list[dict[str, object]] = []
    selected_ids: set[str] = set()
    for selector in selectors:
        token = str(selector).strip()
        if not token:
            raise ValueError("Component selectors must not be empty")
        path_matches = [
            record
            for record in records
            if "/".join(record["path"]) == token or record["node_id"] == token
        ]
        matches = path_matches or [
            record for record in records if record["name"] == token
        ]
        if not matches:
            candidates = sorted(
                {
                    record["name"]
                    for record in records
                    if token.casefold() in str(record["name"]).casefold()
                }
            )[:12]
            suffix = f"; nearby names: {', '.join(candidates)}" if candidates else ""
            raise ValueError(f"No STEP component matches {token!r}{suffix}")
        for record in matches:
            node_id = str(record["node_id"])
            if node_id not in selected_ids:
                selected.append(record)
                selected_ids.add(node_id)
    return selected


def render_step_components_rpath(
    step_path: str | Path,
    component_names: Sequence[str],
    output_path: str | Path,
    *,
    with_context: bool = True,
    title: str | None = None,
    views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS,
    image_size: tuple[float, float] = (18.0, 12.0),
    dpi: int = 180,
    linear_deflection: float = 0.12,
    angular_deflection: float = 0.18,
) -> Path:
    """Render named XCAF component occurrences, optionally in assembly context."""
    source = Path(step_path)
    document, root, _ = _load_step_xcaf_document(source)
    selected = _resolve_step_components(document, component_names)
    shapes = [record["shape"] for record in selected]
    selected_title = ", ".join(str(record["name"]) for record in selected)
    selected_mesh = _mesh_polydata(shapes, linear_deflection, angular_deflection)
    selected_edges = _edge_polydata(shapes, deflection=linear_deflection)
    if with_context:
        return _render_polydata_views(
            _mesh_polydata([root], linear_deflection, angular_deflection),
            output_path,
            title=title or f"{source.name} - {selected_title}",
            views=views,
            image_size=image_size,
            dpi=dpi,
            context_opacity=0.12,
            highlighted_polydata=selected_mesh,
            highlighted_edge_polydata=selected_edges,
        )
    return _render_polydata_views(
        selected_mesh,
        output_path,
        title=title or f"{source.name} - {selected_title}",
        views=views,
        image_size=image_size,
        dpi=dpi,
        brep_edge_polydata=selected_edges,
    )


_NAMED_COLORS: Mapping[str, tuple[float, float, float]] = {
    "red": (0.90, 0.18, 0.20),
    "crimson": (0.86, 0.08, 0.24),
    "orange": (0.95, 0.55, 0.15),
    "gold": (0.85, 0.65, 0.13),
    "yellow": (0.95, 0.85, 0.15),
    "lime": (0.50, 0.80, 0.20),
    "green": (0.20, 0.75, 0.35),
    "teal": (0.15, 0.70, 0.70),


    "cyan": (0.15, 0.85, 0.90),
    "skyblue": (0.40, 0.75, 0.95),
    "blue": (0.20, 0.35, 0.95),
    "navy": (0.15, 0.15, 0.55),
    "purple": (0.55, 0.25, 0.80),
    "violet": (0.60, 0.45, 0.90),
    "magenta": (0.90, 0.15, 0.70),
    "pink": (0.95, 0.30, 0.70),
    "salmon": (0.95, 0.55, 0.45),
    "brown": (0.60, 0.40, 0.20),
    "tan": (0.80, 0.65, 0.45),
    "olive": (0.55, 0.55, 0.20),
    "gray": (0.55, 0.55, 0.55),
    "silver": (0.75, 0.75, 0.78),
    "black": (0.10, 0.10, 0.12),
    "white": (0.96, 0.96, 0.96),
}
def _distinct_entity_colors(count: int) -> list[tuple[float, float, float]]:
    """Return deterministic high-contrast colors with no duplicate RGB values."""
    if count < 0:
        raise ValueError("color count must not be negative")
    colors: list[tuple[float, float, float]] = []
    golden_ratio = 0.6180339887498949
    for index in range(count):
        hue = (0.97 + index * golden_ratio) % 1.0
        saturation = 0.72 if index % 2 == 0 else 0.86
        value = 0.92 if index % 3 else 0.78
        colors.append(tuple(float(channel) for channel in colorsys.hsv_to_rgb(hue, saturation, value)))
    return colors


def _entity_anchor(descriptor: Mapping[str, Any]) -> tuple[float, float, float]:
    geometry = descriptor["geometry"]
    values = geometry.get("centroid") or geometry.get("coordinates")
    if values is None:
        values = descriptor["bounding_box"]["center"]
    return tuple(float(value) for value in values)

def _entity_map_legend(
    entries: Sequence[tuple[str, str, tuple[float, float, float]]],
    *,
    columns: int = 3,
) -> list[tuple[str, tuple[float, float, float]]]:
    """Return compact ID/type rows; columns are populated top-to-bottom."""
    if columns < 1:
        raise ValueError("legend_columns must be at least one")
    return [(f"{entity_id} · {geometry_type}", color) for entity_id, geometry_type, color in entries]


def render_entity_map_rpath(
    model_or_path: BRepModel | TopoDS_Shape | str | Path,
    entity_ids: Sequence[str],
    output_path: str | Path,
    *,
    title: str = "BREP entity map",
    views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS,
    highlight_edge_width: float = 6.0,
    highlight_point_size: float = 18.0,
    image_size: tuple[float, float] = (18.0, 12.0),
    dpi: int = 180,
    linear_deflection: float = 0.12,
    angular_deflection: float = 0.18,
    edge_samples: int = 96,
    context_opacity: float = 1.0,
    label_mode: Literal["auto", "callout", "legend", "none"] = "legend",
    max_callouts: int = 4,
    legend_columns: int = 3,
) -> Path:
    """Render stable BREP entity IDs without flattening model depth.

    The base model stays opaque by default and keeps its true BREP edges.
    Bodies use colored topology edges, faces use a restrained translucent tint
    plus boundary edges, edges use thick curves, and vertices use colored
    points. ``highlight_edge_width`` and ``highlight_point_size`` make selected
    edges and vertices visually dominant. A dedicated ID/type key is the safe
    default; callouts remain available for focused selections.
    """
    if edge_samples < 2:
        raise ValueError("edge_samples must be at least two")
    if not 0.0 <= context_opacity <= 1.0:
        raise ValueError("context_opacity must be between zero and one")
    if label_mode not in {"auto", "callout", "legend", "none"}:
        raise ValueError("label_mode must be auto, callout, legend, or none")
    if max_callouts < 1:
        raise ValueError("max_callouts must be at least one")
    if label_mode == "callout" and len(entity_ids) > max_callouts:
        raise ValueError(
            f"callout mode supports at most {max_callouts} entities; use legend mode"
        )
    if legend_columns < 1:
        raise ValueError("legend_columns must be at least one")
    if not entity_ids:
        raise ValueError("At least one entity ID is required")
    model = (
        model_or_path
        if isinstance(model_or_path, BRepModel)
        else index_shape_rbrepmodel(model_or_path)
        if isinstance(model_or_path, TopoDS_Shape)
        else load_step_rbrepmodel(model_or_path)
    )
    canonical_ids: list[str] = []
    resolved: list[tuple[str, TopoDS_Shape, Mapping[str, Any]]] = []
    seen: set[str] = set()
    for entity_id in entity_ids:
        kind, index, shape = model.resolve_entity(entity_id)
        canonical = f"{kind}:{index}"
        if canonical in seen:
            raise ValueError(f"duplicate entity ID {canonical!r}")
        seen.add(canonical)
        canonical_ids.append(canonical)
        resolved.append((kind, shape, model.describe_entity(canonical)))

    surface_groups: list[tuple[Any, tuple[float, float, float], float]] = []
    edge_groups: list[tuple[Any, tuple[float, float, float]]] = []
    point_groups: list[tuple[Any, tuple[float, float, float]]] = []
    label_entries: list[
        tuple[str, str, tuple[float, float, float]]
    ] = []
    callouts: list[
        tuple[str, tuple[float, float, float], tuple[float, float, float]]
    ] = []
    for canonical, color, (kind, shape, descriptor) in zip(
        canonical_ids,
        _distinct_entity_colors(len(resolved)),
        resolved,
        strict=True,
    ):
        anchor = _entity_anchor(descriptor)
        if kind == "face":
            surface_groups.append(
                (
                    _mesh_polydata(
                        [shape], linear_deflection, angular_deflection
                    ),
                    color,
                    min(0.28, context_opacity),
                )
            )
            edge_groups.append(
                (_edge_polydata([shape], deflection=linear_deflection), color)
            )
        elif kind == "body":
            edge_groups.append(
                (_edge_polydata([shape], deflection=linear_deflection), color)
            )
        elif kind == "edge":
            edge_groups.append(
                (_edge_polydata([shape], sample_count=edge_samples), color)
            )
        point_groups.append((_point_polydata([anchor]), color))
        geometry_type = str(descriptor["geometry"]["type"])
        label_entries.append((canonical, geometry_type, color))
        callouts.append((f"{canonical} · {geometry_type}", anchor, color))

    effective_label_mode = (
        "callout" if label_mode == "auto" and len(resolved) <= max_callouts
        else "legend" if label_mode == "auto"
        else label_mode
    )
    legend = (
        _entity_map_legend(label_entries, columns=legend_columns)
        if effective_label_mode == "legend"
        else None
    )

    return _render_polydata_views(
        _mesh_polydata([model.root], linear_deflection, angular_deflection),
        output_path,
        legend_panel=effective_label_mode == "legend",
        title=title,
        views=views,
        image_size=image_size,
        dpi=dpi,
        context_opacity=context_opacity,
        brep_edge_polydata=_edge_polydata([model.root], deflection=linear_deflection),
        highlighted_groups=surface_groups,
        highlighted_edge_groups=edge_groups,
        highlighted_point_groups=point_groups,
        highlight_edge_width=highlight_edge_width,
        highlight_point_size=highlight_point_size,
        legend=legend,
        legend_columns=legend_columns,
        callouts=callouts if effective_label_mode == "callout" else None,
    )
def render_entity_kind_maps_rpath(
    model_or_path: BRepModel | TopoDS_Shape | str | Path,
    entity_ids: Sequence[str],
    output_dir: str | Path,
    *,
    title: str = "BREP entity map",
    views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS,
    image_size: tuple[float, float] = (18.0, 12.0),
    dpi: int = 180,
    linear_deflection: float = 0.12,
    angular_deflection: float = 0.18,
    edge_samples: int = 96,
    context_opacity: float = 1.0,
    highlight_edge_width: float = 6.0,
    highlight_point_size: float = 18.0,
    label_mode: Literal["auto", "callout", "legend", "none"] = "legend",
    max_callouts: int = 4,
    legend_columns: int = 3,
) -> dict[str, Path]:
    """Render independent face, edge, and vertex highlight maps."""
    if not entity_ids:
        raise ValueError("At least one entity ID is required")
    if isinstance(model_or_path, BRepModel):
        model = model_or_path
    elif isinstance(model_or_path, TopoDS_Shape):
        model = index_shape_rbrepmodel(model_or_path)
    else:
        model = load_step_rbrepmodel(model_or_path)
    grouped: dict[str, list[str]] = {"face": [], "edge": [], "vertex": []}
    for entity_id in entity_ids:
        kind, index, _ = model.resolve_entity(entity_id)
        if kind in grouped:
            grouped[kind].append(f"{kind}:{index}")
    output_root = Path(output_dir)
    result: dict[str, Path] = {}
    for kind, ids in grouped.items():
        if not ids:
            continue
        result[kind] = render_entity_map_rpath(
            model,
            ids,
            output_root / f"{kind}-map.png",
            title=f"{title} · {kind}s",
            views=views,
            image_size=image_size,
            dpi=dpi,
            linear_deflection=linear_deflection,
            angular_deflection=angular_deflection,
            edge_samples=edge_samples,
            context_opacity=context_opacity,
            highlight_edge_width=highlight_edge_width,
            highlight_point_size=highlight_point_size,
            label_mode=label_mode,
            max_callouts=max_callouts,
            legend_columns=legend_columns,
        )
    return result


def _resolve_color(
    spec: ColorSpec,
    palette: Sequence[ColorSpec] | None = None,
) -> tuple[float, float, float]:
    """Resolve a color spec to an (r, g, b) tuple in 0..1."""
    if isinstance(spec, int):
        if palette is None:
            raise ValueError("an integer color requires a palette")
        if spec < 0 or spec >= len(palette):
            raise ValueError(f"palette index {spec} out of range 0..{len(palette) - 1}")
        return _resolve_color(palette[spec])
    if isinstance(spec, str):
        value = spec.strip()
        if value.startswith("#"):
            digits = value[1:]
            if len(digits) == 6:
                return tuple(int(digits[i : i + 2], 16) / 255.0 for i in (0, 2, 4))
            if len(digits) == 3:
                return tuple(int(digits[i] * 2, 16) / 255.0 for i in (0, 1, 2))
            raise ValueError(f"hex color must be #RRGGBB or #RGB, got {spec!r}")
        name = value.casefold()
        if name in _NAMED_COLORS:
            return _NAMED_COLORS[name]
        raise ValueError(
            f"unknown color {spec!r}; use #RRGGBB, a named color "
            f"({', '.join(sorted(_NAMED_COLORS))}), or an (r, g, b) tuple"
        )
    if isinstance(spec, tuple) and len(spec) == 3:
        return tuple(float(channel) for channel in spec)
    raise ValueError(f"invalid color spec {spec!r}")


def render_step_components_colored_rpath(
    step_path: str | Path,
    component_colors: Mapping[str, ColorSpec],
    output_path: str | Path,
    *,
    palette: Sequence[ColorSpec] | None = None,
    with_context: bool = True,
    title: str | None = None,
    views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS,
    image_size: tuple[float, float] = (18.0, 12.0),
    dpi: int = 180,
    linear_deflection: float = 0.12,
    angular_deflection: float = 0.18,
    show_legend: bool = True,
) -> Path:
    """Render multiple STEP components, each in its own color.

    The recommended, most semantic form maps each component selector
    directly to a color NAME::

        render_step_components_colored_rpath(
            "assembly.step",
            {"SPK-2030X4MM": "cyan", "USER_LIBRARY-USB_TYPE_C_PORT__S": "purple"},
            "out.png",
        )

    Selectors resolve like ``render_step_components_rpath`` (names, paths,
    or node ids) and multiple occurrences of one name share its color.
    ``component_colors`` values accept a named color from the built-in set
    (red, crimson, orange, gold, yellow, lime, green, teal, cyan, skyblue,
    blue, navy, purple, violet, magenta, pink, salmon, brown, tan, olive,
    gray, silver, black, white), a ``#RRGGBB`` / ``#RGB`` hex string, an
    ``(r, g, b)`` 0..1 tuple, or an integer palette index (with ``palette``).
    The result shows every selected solid at once, color-coded, with an
    optional color legend so the geometry can be matched to per-component
    text.
    """
    if not component_colors:
        raise ValueError("At least one component color mapping is required")
    source = Path(step_path)
    document, root, _ = _load_step_xcaf_document(source)
    selectors = list(component_colors)
    selected = _resolve_step_components(document, selectors)
    selector_to_records: dict[str, list[dict[str, object]]] = {}
    used: set[str] = set()
    for selector in selectors:
        token = str(selector).strip()
        matches = [
            record
            for record in selected
            if record["node_id"] == token
            or "/".join(record["path"]) == token
            or str(record["name"]) == token
        ]
        if not matches:
            raise ValueError(f"selector {token!r} resolved to no component")
        selector_to_records[token] = matches
        used.update(record["node_id"] for record in matches)
    if len(used) != len(selected):
        unresolved = [
            str(record["name"])
            for record in selected
            if record["node_id"] not in used
        ]
        raise ValueError(f"component colors did not cover selected components: {unresolved}")

    groups: list[tuple[Any, tuple[float, float, float], float]] = []
    edge_groups: list[tuple[Any, tuple[float, float, float]]] = []
    legend: list[tuple[str, tuple[float, float, float]]] = []
    legend_seen: set[tuple[str, tuple[float, float, float]]] = set()
    for selector in selectors:
        spec = component_colors[selector]
        rgb = _resolve_color(spec, palette)
        for record in selector_to_records[str(selector).strip()]:
            shape = record["shape"]
            groups.append(
                (_mesh_polydata([shape], linear_deflection, angular_deflection), rgb, 1.0)
            )
            edge_groups.append((_edge_polydata([shape], deflection=linear_deflection), rgb))
        entry = (f"{str(selector).strip()} ({spec})", rgb)
        if show_legend and entry not in legend_seen:
            legend.append(entry)
            legend_seen.add(entry)

    if with_context:
        return _render_polydata_views(
            _mesh_polydata([root], linear_deflection, angular_deflection),
            output_path,
            title=title or f"{source.name} - colored components",
            views=views,
            image_size=image_size,
            dpi=dpi,
            context_opacity=0.12,
            highlighted_groups=groups,
            highlighted_edge_groups=edge_groups,
            legend=legend,
        )
    return _render_polydata_views(
        None,
        output_path,
        title=title or f"{source.name} - colored components",
        views=views,
        image_size=image_size,
        dpi=dpi,
        highlighted_groups=groups,
        highlighted_edge_groups=edge_groups,
        legend=legend,
    )


def render_step_views_rpath(
    step_path: str | Path,
    output_path: str | Path,
    **kwargs,
) -> Path:
    """Load STEP/XCAF colors and render smooth faces with true BREP edges."""
    source = Path(step_path)
    kwargs.setdefault("title", f"{source.name} - BREP views")
    shape, face_colors = _load_step_xcaf(source)
    views = kwargs.pop("views", DEFAULT_VIEWS)
    image_size = kwargs.pop("image_size", (18.0, 12.0))
    dpi = kwargs.pop("dpi", 180)
    linear_deflection = kwargs.pop("linear_deflection", 0.12)
    angular_deflection = kwargs.pop("angular_deflection", 0.18)
    show_brep_edges = kwargs.pop("show_brep_edges", True)
    title = kwargs.pop("title")
    if kwargs:
        unknown = ", ".join(sorted(kwargs))
        raise TypeError(f"Unexpected render options: {unknown}")
    return _render_polydata_views(
        _mesh_polydata(
            [shape],
            linear_deflection,
            angular_deflection,
            face_colors=face_colors,
        ),
        output_path,
        title=title,
        views=views,
        image_size=image_size,
        dpi=dpi,
        brep_edge_polydata=(
            _edge_polydata([shape], deflection=linear_deflection)
            if show_brep_edges
            else None
        ),
    )


def render_region_rpath(
    model_or_path: BRepModel | TopoDS_Shape | str | Path,
    entity_ids: Sequence[str],
    output_path: str | Path,
    *,
    neighborhood_depth: int = 0,
    title: str = "Highlighted BREP region",
    views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS,
    image_size: tuple[float, float] = (18.0, 12.0),
    dpi: int = 180,
    linear_deflection: float = 0.12,
    angular_deflection: float = 0.18,
    edge_samples: int = 96,
    highlight_edge_width: float = 6.0,
    highlight_point_size: float = 18.0,
) -> Path:
    """Highlight stable entities and their optional topology neighborhood."""
    if edge_samples < 2:
        raise ValueError("edge_samples must be at least two")
    if isinstance(model_or_path, BRepModel):
        model = model_or_path
    elif isinstance(model_or_path, TopoDS_Shape):
        model = index_shape_rbrepmodel(model_or_path)
    else:
        model = load_step_rbrepmodel(model_or_path)

    from .queries import select_region_entities_rdescriptor

    selection = select_region_entities_rdescriptor(
        model,
        entity_ids=entity_ids,
        depth=neighborhood_depth,
    )
    selected_ids = selection["entity_ids"]
    if not selected_ids:
        raise ValueError("No entities were selected for rendering")

    selected_faces = TopTools_IndexedMapOfShape()
    selected_edges: list[TopoDS_Shape] = []
    selected_points: list[tuple[float, float, float]] = []
    for entity_id in selected_ids:
        kind, _, shape = model.resolve_entity(entity_id)
        if kind == "body":
            explorer = TopExp_Explorer(shape, TopAbs_FACE)
            while explorer.More():
                selected_faces.Add(explorer.Current())
                explorer.Next()
        elif kind == "face":
            selected_faces.Add(shape)
        elif kind == "edge":
            selected_edges.append(shape)
        else:
            point = BRep_Tool.Pnt_s(TopoDS.Vertex_s(shape))
            selected_points.append(
                (float(point.X()), float(point.Y()), float(point.Z()))
            )

    face_shapes = [
        selected_faces.FindKey(index)
        for index in range(1, selected_faces.Extent() + 1)
    ]
    highlighted = (
        _mesh_polydata(face_shapes, linear_deflection, angular_deflection)
        if face_shapes
        else None
    )
    highlighted_edges = _edge_polydata(
        selected_edges,
        sample_count=edge_samples,
    )
    highlighted_points = _point_polydata(selected_points)
    return _render_polydata_views(
        _mesh_polydata([model.root], linear_deflection, angular_deflection),
        output_path,
        title=f"{title} ({', '.join(selected_ids)})",
        views=views,
        image_size=image_size,
        dpi=dpi,
        context_opacity=0.18,
        highlighted_polydata=highlighted,
        highlighted_edge_polydata=highlighted_edges,
        highlight_edge_width=highlight_edge_width,
        highlight_point_size=highlight_point_size,
        highlighted_point_polydata=highlighted_points,
    )
