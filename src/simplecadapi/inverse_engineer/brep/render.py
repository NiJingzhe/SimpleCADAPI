"""Consistent multi-view rendering for BREP inspection."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopAbs import TopAbs_FACE, TopAbs_VERTEX
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Edge, TopoDS_Shape

from .inspect import inspect_shape
from .io import load_step
from .model import BRepModel, index_shape, load_step_model

DEFAULT_VIEWS: tuple[tuple[float, float, str], ...] = (
    (25.0, -55.0, "isometric"),
    (0.0, -90.0, "top / X-Z"),
    (90.0, -90.0, "front / X-Y"),
    (0.0, 0.0, "side / Y-Z"),
)


def _triangles(
    shape: TopoDS_Shape, linear_deflection: float, angular_deflection: float
):
    BRepMesh_IncrementalMesh(shape, linear_deflection, False, angular_deflection, True)
    polygons: list[list[tuple[float, float, float]]] = []
    explorer = TopExp_Explorer(shape, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        location = face.Location()
        triangulation = BRep_Tool.Triangulation_s(face, location)
        if triangulation is not None and triangulation.NbTriangles() > 0:
            for index in range(1, triangulation.NbTriangles() + 1):
                triangle = triangulation.Triangle(index)
                points: list[tuple[float, float, float]] = []
                for node_index in (
                    triangle.Value(1),
                    triangle.Value(2),
                    triangle.Value(3),
                ):
                    point = triangulation.Node(node_index)
                    point.Transform(location.Transformation())
                    points.append(
                        (float(point.X()), float(point.Y()), float(point.Z()))
                    )
                polygons.append(points)
        explorer.Next()
    return polygons


def render_shape_views(
    shape: TopoDS_Shape,
    output_path: str | Path,
    *,
    title: str = "BREP views",
    views: Sequence[tuple[float, float, str]] = DEFAULT_VIEWS,
    image_size: tuple[float, float] = (18.0, 12.0),
    dpi: int = 180,
    linear_deflection: float = 0.12,
    angular_deflection: float = 0.18,
) -> Path:
    """Render one BREP from consistent Matplotlib 3D camera angles.

    Matplotlib is imported lazily because visualization is an optional
    diagnostic and is not needed for strict geometry/topology inspection.
    """
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except ImportError as error:
        raise ImportError("render_shape_views requires matplotlib") from error

    polygons = _triangles(shape, linear_deflection, angular_deflection)
    report = inspect_shape(shape)
    x0, y0, z0, x1, y1, z1 = report.bounding_box
    spans = np.maximum(np.asarray([x1 - x0, y1 - y0, z1 - z0]), 1.0e-9)
    margins = np.maximum(spans * 0.05, 1.0e-6)

    columns = 2
    rows = (len(views) + columns - 1) // columns
    figure = plt.figure(figsize=image_size)
    for index, (elevation, azimuth, view_title) in enumerate(views, 1):
        axes = figure.add_subplot(rows, columns, index, projection="3d")
        axes.add_collection3d(
            Poly3DCollection(
                polygons,
                facecolor="#b9c7d6",
                edgecolor="#435466",
                linewidth=0.12,
                alpha=1.0,
            )
        )
        axes.view_init(elev=elevation, azim=azimuth)
        axes.set_title(view_title)
        axes.set_xlabel("X")
        axes.set_ylabel("Y")
        axes.set_zlabel("Z")
        axes.set_box_aspect(tuple(float(value) for value in spans))
        axes.set_xlim(x0 - margins[0], x1 + margins[0])
        axes.set_ylim(y0 - margins[1], y1 + margins[1])
        axes.set_zlim(z0 - margins[2], z1 + margins[2])
    figure.suptitle(title)
    figure.tight_layout()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=dpi)
    plt.close(figure)
    return output


def render_step_views(
    step_path: str | Path,
    output_path: str | Path,
    **kwargs,
) -> Path:
    """Load a STEP file and render consistent BREP views."""
    source = Path(step_path)
    kwargs.setdefault("title", f"{source.name} - BREP views")
    return render_shape_views(load_step(source), output_path, **kwargs)


def _sample_highlight_edge(
    edge: TopoDS_Edge,
    sample_count: int,
) -> list[tuple[float, float, float]]:
    if BRep_Tool.Degenerated_s(edge):
        explorer = TopExp_Explorer(edge, TopAbs_VERTEX)
        if not explorer.More():
            return []
        point = BRep_Tool.Pnt_s(TopoDS.Vertex_s(explorer.Current()))
        return [(float(point.X()), float(point.Y()), float(point.Z()))]
    adaptor = BRepAdaptor_Curve(edge)
    first = float(adaptor.FirstParameter())
    last = float(adaptor.LastParameter())
    return [
        tuple(float(value) for value in adaptor.Value(float(parameter)).Coord())
        for parameter in np.linspace(first, last, sample_count)
    ]


def render_region(
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
) -> Path:
    """Highlight stable entities and their optional topology neighborhood."""

    if edge_samples < 2:
        raise ValueError("edge_samples must be at least two")
    if isinstance(model_or_path, BRepModel):
        model = model_or_path
    elif isinstance(model_or_path, TopoDS_Shape):
        model = index_shape(model_or_path)
    else:
        model = load_step_model(model_or_path)

    from .queries import select_region_entities

    selection = select_region_entities(
        model,
        entity_ids=entity_ids,
        depth=neighborhood_depth,
    )
    selected_ids = selection["entity_ids"]
    if not selected_ids:
        raise ValueError("No entities were selected for rendering")

    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        from mpl_toolkits.mplot3d.art3d import Poly3DCollection
    except ImportError as error:
        raise ImportError("render_region requires matplotlib") from error

    base_polygons = _triangles(
        model.root,
        linear_deflection,
        angular_deflection,
    )
    highlighted_polygons = []
    highlighted_lines = []
    highlighted_points = []
    for entity_id in selected_ids:
        kind, _, shape = model.resolve_entity(entity_id)
        if kind in {"body", "face"}:
            highlighted_polygons.extend(
                _triangles(shape, linear_deflection, angular_deflection)
            )
        elif kind == "edge":
            points = _sample_highlight_edge(TopoDS.Edge_s(shape), edge_samples)
            if len(points) == 1:
                highlighted_points.extend(points)
            elif points:
                highlighted_lines.append(points)
        else:
            point = BRep_Tool.Pnt_s(TopoDS.Vertex_s(shape))
            highlighted_points.append(
                (float(point.X()), float(point.Y()), float(point.Z()))
            )

    report = inspect_shape(model.root)
    x0, y0, z0, x1, y1, z1 = report.bounding_box
    spans = np.maximum(np.asarray([x1 - x0, y1 - y0, z1 - z0]), 1.0e-9)
    margins = np.maximum(spans * 0.05, 1.0e-6)
    columns = 2
    rows = (len(views) + columns - 1) // columns
    figure = plt.figure(figsize=image_size)
    for index, (elevation, azimuth, view_title) in enumerate(views, 1):
        axes = figure.add_subplot(rows, columns, index, projection="3d")
        axes.add_collection3d(
            Poly3DCollection(
                base_polygons,
                facecolor="#b9c7d6",
                edgecolor="#435466",
                linewidth=0.12,
                alpha=0.8,
            )
        )
        if highlighted_polygons:
            axes.add_collection3d(
                Poly3DCollection(
                    highlighted_polygons,
                    facecolor="#ef476f",
                    edgecolor="#9d112d",
                    linewidth=0.5,
                    alpha=0.95,
                )
            )
        for line in highlighted_lines:
            values = np.asarray(line)
            axes.plot(
                values[:, 0],
                values[:, 1],
                values[:, 2],
                color="#d00000",
                linewidth=2.2,
            )
        if highlighted_points:
            values = np.asarray(highlighted_points)
            axes.scatter(
                values[:, 0],
                values[:, 1],
                values[:, 2],
                color="#d00000",
                s=30,
                depthshade=False,
            )
        axes.view_init(elev=elevation, azim=azimuth)
        axes.set_title(view_title)
        axes.set_xlabel("X")
        axes.set_ylabel("Y")
        axes.set_zlabel("Z")
        axes.set_box_aspect(tuple(float(value) for value in spans))
        axes.set_xlim(x0 - margins[0], x1 + margins[0])
        axes.set_ylim(y0 - margins[1], y1 + margins[1])
        axes.set_zlim(z0 - margins[2], z1 + margins[2])
    figure.suptitle(f"{title} ({', '.join(selected_ids)})")
    figure.tight_layout()
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.savefig(output, dpi=dpi)
    plt.close(figure)
    return output
