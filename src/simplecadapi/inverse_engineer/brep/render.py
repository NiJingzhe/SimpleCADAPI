"""Consistent multi-view rendering for BREP inspection."""

from __future__ import annotations

from pathlib import Path
from typing import Sequence

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS, TopoDS_Shape

from .inspect import inspect_shape
from .io import load_step

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
