"""Convert CalculiX FRD results to ParaView VTU and render a stress preview."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import importlib
from pathlib import Path
from typing import Any


OUT_DIR = Path(__file__).resolve().parent / "out"
FRD_PATH = OUT_DIR / "ap242_gmsh_bracket_static.frd"
MESH_PATH = OUT_DIR / "ap242_gmsh_bracket.msh"
PNG_PATH = OUT_DIR / "ap242_gmsh_bracket_static_von_mises.png"
DEFAULT_DEFORMATION_SCALE = 120.0
LOAD_INTERFACE = "interface.load_surface"
DEFAULT_LOAD_Z_N = -1_000.0


@dataclass(frozen=True, slots=True)
class CalculiXVisualizationReport:
    frd_path: Path
    vtu_path: Path
    png_path: Path
    displacement_field: str
    stress_field: str
    deformation_scale: float
    visualized_max_von_mises_mpa: float
    load_surface_triangle_count: int
    load_arrow_count: int
    applied_load_z_n: float


def _optional_module(name: str, message: str) -> Any:
    try:
        return importlib.import_module(name)
    except ImportError as exc:
        raise RuntimeError(message) from exc


def _converted_vtu_path(frd_path: Path) -> Path:
    direct = frd_path.with_suffix(".vtu")
    if direct.is_file():
        return direct
    candidates = sorted(
        frd_path.parent.glob(f"{frd_path.stem}*.vtu"),
        key=lambda path: path.stat().st_mtime_ns,
        reverse=True,
    )
    if not candidates:
        raise RuntimeError(f"ccx2paraview created no VTU file for {frd_path}")
    return candidates[0]


def convert_frd_to_vtu(
    frd_path: str | Path,
    *,
    converter_class: Any | None = None,
) -> Path:
    """Convert one ASCII CalculiX FRD result to modern ParaView VTU."""

    source = Path(frd_path).expanduser().resolve()
    if not source.is_file() or source.stat().st_size <= 0:
        raise FileNotFoundError(f"Run run_calculix.py first: {source}")
    if converter_class is None:
        package = _optional_module(
            "ccx2paraview",
            "CalculiX visualization is optional; install it with "
            "`pip install simplecadapi[fem]`",
        )
        converter_class = package.Converter
    converter_class(str(source), ["vtu"]).run()
    destination = _converted_vtu_path(source)
    if destination.stat().st_size <= 0:
        raise RuntimeError(f"ccx2paraview created an empty VTU file: {destination}")
    return destination


def _point_array_names(dataset: Any) -> list[str]:
    point_data = dataset.GetPointData()
    return [
        str(point_data.GetArrayName(index))
        for index in range(point_data.GetNumberOfArrays())
    ]


def _load_surface_mesh(
    mesh_path: Path,
    *,
    gmsh_module: Any | None = None,
) -> tuple[dict[int, tuple[float, float, float]], list[tuple[int, int, int]]]:
    gmsh = gmsh_module or _optional_module(
        "gmsh",
        "Load visualization requires Gmsh; install it with `pip install simplecadapi[fem]`",
    )
    initialized = False
    try:
        gmsh.initialize()
        initialized = True
        gmsh.open(str(mesh_path))
        groups = [
            int(tag)
            for dimension, tag in gmsh.model.getPhysicalGroups(2)
            if gmsh.model.getPhysicalName(dimension, tag) == LOAD_INTERFACE
        ]
        if len(groups) != 1:
            raise RuntimeError(
                f"mesh must contain one physical group named {LOAD_INTERFACE!r}"
            )
        node_tags, coordinates, _parameters = gmsh.model.mesh.getNodes()
        values = list(float(value) for value in coordinates)
        points = {
            int(tag): (values[index], values[index + 1], values[index + 2])
            for tag, index in zip(node_tags, range(0, len(values), 3))
        }
        triangle_type = int(gmsh.model.mesh.getElementType("Triangle", 1))
        triangles: list[tuple[int, int, int]] = []
        for entity in gmsh.model.getEntitiesForPhysicalGroup(2, groups[0]):
            _element_tags, node_ids = gmsh.model.mesh.getElementsByType(
                triangle_type,
                int(entity),
            )
            ids = [int(value) for value in node_ids]
            triangles.extend(
                (ids[index], ids[index + 1], ids[index + 2])
                for index in range(0, len(ids), 3)
            )
        if not triangles:
            raise RuntimeError(f"physical group {LOAD_INTERFACE!r} has no triangles")
        return points, triangles
    finally:
        if initialized:
            gmsh.finalize()


def _sample_centroids(
    centroids: list[tuple[float, float, float]],
    count: int,
) -> list[tuple[float, float, float]]:
    if len(centroids) <= count:
        return centroids
    selected = [max(centroids, key=lambda point: point[0] + point[1])]
    remaining = set(centroids)
    remaining.remove(selected[0])
    while remaining and len(selected) < count:
        next_point = max(
            remaining,
            key=lambda point: min(
                sum((point[index] - chosen[index]) ** 2 for index in range(3))
                for chosen in selected
            ),
        )
        selected.append(next_point)
        remaining.remove(next_point)
    return selected


def _load_condition_actors(
    vtk: Any,
    dataset: Any,
    mesh_path: Path,
    displacement_field: str,
    deformation_scale: float,
    applied_load_z_n: float,
) -> tuple[Any, Any, Any, int, int]:
    source_points, triangles = _load_surface_mesh(mesh_path)
    locator = vtk.vtkPointLocator()
    locator.SetDataSet(dataset)
    locator.BuildLocator()
    displacement = dataset.GetPointData().GetArray(displacement_field)

    used_nodes = sorted({node for triangle in triangles for node in triangle})
    local_index = {node: index for index, node in enumerate(used_nodes)}
    warped_points: dict[int, tuple[float, float, float]] = {}
    vtk_points = vtk.vtkPoints()
    for node in used_nodes:
        original = source_points[node]
        point_index = locator.FindClosestPoint(original)
        matched = dataset.GetPoint(point_index)
        distance_sq = sum((matched[index] - original[index]) ** 2 for index in range(3))
        if distance_sq > 1.0e-8:
            raise RuntimeError(
                f"could not map load-surface node {node} into CalculiX VTU"
            )
        vector = displacement.GetTuple3(point_index)
        warped_point = tuple(
            original[index] + deformation_scale * vector[index]
            for index in range(3)
        )
        warped_points[node] = warped_point
        vtk_points.InsertNextPoint(warped_point)

    cells = vtk.vtkCellArray()
    centroids: list[tuple[float, float, float]] = []
    for triangle in triangles:
        cell = vtk.vtkTriangle()
        for index, node in enumerate(triangle):
            cell.GetPointIds().SetId(index, local_index[node])
        cells.InsertNextCell(cell)
        centroids.append(
            tuple(
                sum(warped_points[node][axis] for node in triangle) / 3.0
                for axis in range(3)
            )
        )
    load_surface = vtk.vtkPolyData()
    load_surface.SetPoints(vtk_points)
    load_surface.SetPolys(cells)
    boundary = vtk.vtkFeatureEdges()
    boundary.SetInputData(load_surface)
    boundary.BoundaryEdgesOn()
    boundary.FeatureEdgesOff()
    boundary.ManifoldEdgesOff()
    boundary.NonManifoldEdgesOff()
    boundary.Update()
    outline = vtk.vtkTubeFilter()
    outline.SetInputConnection(boundary.GetOutputPort())
    outline.SetRadius(0.10)
    outline.SetNumberOfSides(12)
    outline.Update()
    surface_mapper = vtk.vtkPolyDataMapper()
    surface_mapper.SetInputConnection(outline.GetOutputPort())
    surface_mapper.ScalarVisibilityOff()
    surface_actor = vtk.vtkActor()
    surface_actor.SetMapper(surface_mapper)
    surface_actor.GetProperty().SetColor(1.0, 0.78, 0.0)
    surface_actor.GetProperty().LightingOff()
    arrow_centroids = _sample_centroids(centroids, 12)
    arrow_points = vtk.vtkPoints()
    arrow_vectors = vtk.vtkFloatArray()
    arrow_vectors.SetName("force_direction")
    arrow_vectors.SetNumberOfComponents(3)
    arrow_length = 6.0
    for centroid in arrow_centroids:
        arrow_points.InsertNextPoint(
            centroid[0], centroid[1], centroid[2] + arrow_length
        )
        arrow_vectors.InsertNextTuple3(0.0, 0.0, -1.0)
    arrow_polydata = vtk.vtkPolyData()
    arrow_polydata.SetPoints(arrow_points)
    arrow_polydata.GetPointData().SetVectors(arrow_vectors)
    arrow_source = vtk.vtkArrowSource()
    arrow_source.SetTipResolution(20)
    arrow_source.SetShaftResolution(20)
    glyph = vtk.vtkGlyph3D()
    glyph.SetInputData(arrow_polydata)
    glyph.SetSourceConnection(arrow_source.GetOutputPort())
    glyph.SetVectorModeToUseVector()
    glyph.SetScaleModeToScaleByVector()
    glyph.SetScaleFactor(arrow_length)
    glyph.OrientOn()
    glyph.Update()
    arrow_mapper = vtk.vtkPolyDataMapper()
    arrow_mapper.SetInputConnection(glyph.GetOutputPort())
    arrow_mapper.ScalarVisibilityOff()
    arrow_actor = vtk.vtkActor()
    arrow_actor.SetMapper(arrow_mapper)
    arrow_actor.GetProperty().SetColor(0.88, 0.05, 0.12)

    legend = vtk.vtkTextActor()
    legend.SetInput(
        f"LOAD Fz: {applied_load_z_n:.0f} N\nBOUNDARY: yellow\nDIRECTION: -Z"
    )
    legend.SetPosition(24, 24)
    legend.GetTextProperty().SetFontSize(18)
    legend.GetTextProperty().SetBold(True)
    legend.GetTextProperty().SetColor(0.45, 0.02, 0.04)
    return surface_actor, arrow_actor, legend, len(triangles), len(arrow_centroids)

def render_von_mises_preview(
    vtu_path: str | Path,
    png_path: str | Path,
    *,
    mesh_path: str | Path = MESH_PATH,
    deformation_scale: float = DEFAULT_DEFORMATION_SCALE,
    applied_load_z_n: float = DEFAULT_LOAD_Z_N,
    vtk_module: Any | None = None,
) -> CalculiXVisualizationReport:
    """Render the displaced mesh, colored by nodal-extrapolated von Mises stress."""

    if deformation_scale < 0.0:
        raise ValueError("deformation_scale must be nonnegative")
    source = Path(vtu_path).expanduser().resolve()
    destination = Path(png_path).expanduser().resolve()
    if not source.is_file() or source.stat().st_size <= 0:
        raise FileNotFoundError(f"ParaView VTU result is missing: {source}")
    vtk = vtk_module or _optional_module(
        "vtk",
        "VTK rendering is optional; install it with `pip install simplecadapi[fem]`",
    )

    reader = vtk.vtkXMLUnstructuredGridReader()
    reader.SetFileName(str(source))
    reader.Update()
    dataset = reader.GetOutput()
    if dataset is None or dataset.GetNumberOfPoints() <= 0:
        raise RuntimeError(f"VTK read no points from {source}")
    arrays = _point_array_names(dataset)
    displacement_field = "U" if "U" in arrays else "DISP"
    stress_field = "S_Mises" if "S_Mises" in arrays else "S_Mises_Magnitude"
    if displacement_field not in arrays:
        raise RuntimeError(f"VTU has no displacement field; point arrays: {arrays}")
    if stress_field not in arrays:
        raise RuntimeError(f"VTU has no von Mises field; point arrays: {arrays}")

    warp = vtk.vtkWarpVector()
    warp.SetInputData(dataset)
    warp.SetInputArrayToProcess(0, 0, 0, 0, displacement_field)
    warp.SetScaleFactor(float(deformation_scale))
    warp.Update()
    warped = warp.GetOutput()
    stress = warped.GetPointData().GetArray(stress_field)
    stress_range = stress.GetRange()

    surface = vtk.vtkDataSetSurfaceFilter()
    surface.SetInputData(warped)
    surface.Update()
    mapper = vtk.vtkPolyDataMapper()
    mapper.SetInputConnection(surface.GetOutputPort())
    mapper.SetScalarModeToUsePointFieldData()
    mapper.SelectColorArray(stress_field)
    mapper.SetScalarRange(stress_range)

    lookup = vtk.vtkLookupTable()
    lookup.SetNumberOfTableValues(256)
    lookup.SetHueRange(0.667, 0.0)
    lookup.Build()
    mapper.SetLookupTable(lookup)

    actor = vtk.vtkActor()
    actor.SetMapper(mapper)
    actor.GetProperty().EdgeVisibilityOff()

    scalar_bar = vtk.vtkScalarBarActor()
    scalar_bar.SetLookupTable(lookup)
    scalar_bar.SetTitle("von Mises [MPa]")
    scalar_bar.SetNumberOfLabels(5)

    load_surface_actor, arrow_actor, legend, load_triangle_count, arrow_count = (
        _load_condition_actors(
            vtk,
            dataset,
            Path(mesh_path).expanduser().resolve(),
            displacement_field,
            float(deformation_scale),
            float(applied_load_z_n),
        )
    )
    renderer = vtk.vtkRenderer()
    renderer.SetBackground(0.96, 0.97, 0.98)
    renderer.AddActor(actor)
    renderer.AddViewProp(scalar_bar)
    renderer.AddActor(load_surface_actor)
    renderer.AddActor(arrow_actor)
    renderer.AddViewProp(legend)
    renderer.ResetCamera()
    camera = renderer.GetActiveCamera()
    camera.Azimuth(35.0)
    camera.Elevation(22.0)
    camera.Zoom(1.2)

    window = vtk.vtkRenderWindow()
    window.SetOffScreenRendering(1)
    window.SetSize(1280, 900)
    window.AddRenderer(renderer)
    window.Render()

    capture = vtk.vtkWindowToImageFilter()
    capture.SetInput(window)
    capture.SetInputBufferTypeToRGBA()
    capture.ReadFrontBufferOff()
    capture.Update()
    destination.parent.mkdir(parents=True, exist_ok=True)
    writer = vtk.vtkPNGWriter()
    writer.SetFileName(str(destination))
    writer.SetInputConnection(capture.GetOutputPort())
    writer.Write()
    if not destination.is_file() or destination.stat().st_size <= 0:
        raise RuntimeError(f"VTK did not create a non-empty preview at {destination}")

    return CalculiXVisualizationReport(
        frd_path=source.with_suffix(".frd"),
        vtu_path=source,
        png_path=destination,
        displacement_field=displacement_field,
        stress_field=stress_field,
        deformation_scale=float(deformation_scale),
        visualized_max_von_mises_mpa=float(stress_range[1]),
        load_surface_triangle_count=load_triangle_count,
        load_arrow_count=arrow_count,
        applied_load_z_n=float(applied_load_z_n),
    )


def visualize_calculix_result(
    frd_path: str | Path,
    png_path: str | Path,
    *,
    mesh_path: str | Path = MESH_PATH,
    deformation_scale: float = DEFAULT_DEFORMATION_SCALE,
    applied_load_z_n: float = DEFAULT_LOAD_Z_N,
    converter_class: Any | None = None,
    vtk_module: Any | None = None,
) -> CalculiXVisualizationReport:
    vtu_path = convert_frd_to_vtu(frd_path, converter_class=converter_class)
    report = render_von_mises_preview(
        vtu_path,
        png_path,
        deformation_scale=deformation_scale,
        mesh_path=mesh_path,
        applied_load_z_n=applied_load_z_n,
        vtk_module=vtk_module,
    )
    return CalculiXVisualizationReport(
        frd_path=Path(frd_path).expanduser().resolve(),
        vtu_path=report.vtu_path,
        png_path=report.png_path,
        displacement_field=report.displacement_field,
        stress_field=report.stress_field,
        deformation_scale=report.deformation_scale,
        visualized_max_von_mises_mpa=report.visualized_max_von_mises_mpa,
        load_surface_triangle_count=report.load_surface_triangle_count,
        load_arrow_count=report.load_arrow_count,
        applied_load_z_n=report.applied_load_z_n,
    )


def main(
    *,
    frd_path: Path = FRD_PATH,
    png_path: Path = PNG_PATH,
    mesh_path: Path = MESH_PATH,
    applied_load_z_n: float = DEFAULT_LOAD_Z_N,
    deformation_scale: float = DEFAULT_DEFORMATION_SCALE,
) -> None:
    report = visualize_calculix_result(
        frd_path,
        png_path,
        deformation_scale=deformation_scale,
        mesh_path=mesh_path,
        applied_load_z_n=applied_load_z_n,
    )
    print("paraview_vtu", report.vtu_path)
    print("stress_preview", report.png_path)
    print("displacement_field", report.displacement_field)
    print("stress_field", report.stress_field)
    print("deformation_scale", f"{report.deformation_scale:.9g}")
    print("visualized_max_von_mises_mpa", f"{report.visualized_max_von_mises_mpa:.9g}")
    print("load_surface_triangles", report.load_surface_triangle_count)
    print("load_arrows", report.load_arrow_count)
    print("applied_load_z_n", f"{report.applied_load_z_n:.9g}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frd", type=Path, default=FRD_PATH)
    parser.add_argument("--mesh", type=Path, default=MESH_PATH)
    parser.add_argument("--load-z", type=float, default=DEFAULT_LOAD_Z_N)
    parser.add_argument("--png", type=Path, default=PNG_PATH)
    parser.add_argument("--deformation-scale", type=float, default=DEFAULT_DEFORMATION_SCALE)
    arguments = parser.parse_args()
    main(
        frd_path=arguments.frd,
        png_path=arguments.png,
        mesh_path=arguments.mesh,
        applied_load_z_n=arguments.load_z,
        deformation_scale=arguments.deformation_scale,
    )
