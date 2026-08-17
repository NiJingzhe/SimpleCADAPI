"""Shared OpenCASCADE BREP tessellation for STL and OBJ exporters."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Any, Sequence

import numpy as np
from OCP.BRep import BRep_Tool
from OCP.BRepMesh import BRepMesh_IncrementalMesh
from OCP.BRepTools import BRepTools
from OCP.TopAbs import TopAbs_FACE, TopAbs_REVERSED
from OCP.TopExp import TopExp_Explorer
from OCP.TopLoc import TopLoc_Location
from OCP.TopoDS import TopoDS

from ..artifacts.assembly_io import materialize_definition
from ..kernel.ocp_booleans import solids_of
from ..operations import make_compound_from_assembly_rcompound
from ..product import Assembly, Part
from ..translator.package_units import (
    ProductPackageInput,
    read_product_package_translation_units,
)

_TESSELLATION_BACKEND = "opencascade-brep-tessellation"


@dataclass(frozen=True, slots=True)
class TessellatedSurfaceMesh:
    """One triangle mesh produced directly from evaluated product BREP solids."""

    vertices: np.ndarray
    triangles: np.ndarray
    root_definition_id: str
    solid_count: int
    definition_count: int
    linear_deflection: float
    angular_deflection_degrees: float
    relative: bool
    tessellation_backend: str = _TESSELLATION_BACKEND

    @property
    def vertex_count(self) -> int:
        return int(self.vertices.shape[0])

    @property
    def triangle_count(self) -> int:
        return int(self.triangles.shape[0])


def _product_solids(value: Part | Assembly) -> tuple[Any, ...]:
    if isinstance(value, Part):
        return (value.body.wrapped,)
    projection = make_compound_from_assembly_rcompound(assembly=value)
    solids = tuple(solids_of(projection.wrapped))
    if not solids:
        raise ValueError("Product assembly produced no solids for mesh export")
    return solids


def _vertex_key(point: Sequence[float], tolerance: float) -> tuple[int, int, int]:
    return tuple(int(round(float(value) / tolerance)) for value in point)


def _is_collapsed_triangle(
    vertices: Sequence[tuple[float, float, float]],
    indices: tuple[int, int, int],
) -> bool:
    points = np.asarray([vertices[index] for index in indices], dtype=np.float64)
    first = points[1] - points[0]
    second = points[2] - points[0]
    third = points[2] - points[1]
    max_edge_squared = max(
        float(np.dot(first, first)),
        float(np.dot(second, second)),
        float(np.dot(third, third)),
    )
    if max_edge_squared == 0.0:
        return True
    normal = np.cross(first, second)
    area_squared = float(np.dot(normal, normal))
    relative_floor = np.finfo(np.float64).eps ** 2 * max_edge_squared**2
    return area_squared <= relative_floor


def _tessellate_solid(
    solid: Any,
    *,
    linear_deflection: float,
    angular_deflection_radians: float,
    relative: bool,
) -> tuple[np.ndarray, np.ndarray]:
    BRepTools.Clean_s(solid, False)
    mesher = BRepMesh_IncrementalMesh(
        solid,
        linear_deflection,
        relative,
        angular_deflection_radians,
        False,
    )
    mesher.Perform()
    if not mesher.IsDone():
        raise RuntimeError("OpenCASCADE failed to tessellate product geometry")

    weld_tolerance = max(min(linear_deflection * 1.0e-7, 1.0e-7), 1.0e-9)
    vertices: list[tuple[float, float, float]] = []
    vertex_indices: dict[tuple[int, int, int], int] = {}
    triangles: list[tuple[int, int, int]] = []
    explorer = TopExp_Explorer(solid, TopAbs_FACE)
    while explorer.More():
        face = TopoDS.Face_s(explorer.Current())
        location = TopLoc_Location()
        triangulation = BRep_Tool.Triangulation_s(face, location, 0)
        if triangulation is None or triangulation.NbTriangles() == 0:
            raise RuntimeError("OpenCASCADE produced an empty face triangulation")
        transform = location.Transformation()
        local_indices: dict[int, int] = {}
        for node_index in range(1, triangulation.NbNodes() + 1):
            point = triangulation.Node(node_index).Transformed(transform)
            coordinates = (float(point.X()), float(point.Y()), float(point.Z()))
            if not all(math.isfinite(value) for value in coordinates):
                raise RuntimeError("OpenCASCADE produced a non-finite mesh vertex")
            key = _vertex_key(coordinates, weld_tolerance)
            global_index = vertex_indices.get(key)
            if global_index is None:
                global_index = len(vertices)
                vertex_indices[key] = global_index
                vertices.append(coordinates)
            local_indices[node_index] = global_index

        reversed_face = face.Orientation() == TopAbs_REVERSED
        for triangle_index in range(1, triangulation.NbTriangles() + 1):
            a, b, c = triangulation.Triangle(triangle_index).Get()
            indices = (
                (local_indices[a], local_indices[c], local_indices[b])
                if reversed_face
                else (local_indices[a], local_indices[b], local_indices[c])
            )
            if len(set(indices)) == 3 and not _is_collapsed_triangle(vertices, indices):
                triangles.append(indices)
        explorer.Next()

    if not vertices or not triangles:
        raise RuntimeError("OpenCASCADE produced no product surface triangles")
    return (
        np.asarray(vertices, dtype=np.float64).reshape((-1, 3)),
        np.asarray(triangles, dtype=np.int32).reshape((-1, 3)),
    )


def tessellate_product_surface(
    data: ProductPackageInput,
    *,
    linear_deflection: float,
    angular_deflection_degrees: float,
    relative: bool,
) -> TessellatedSurfaceMesh:
    """Tessellate every evaluated product solid directly with OpenCASCADE."""

    linear = float(linear_deflection)
    if not math.isfinite(linear) or linear <= 0.0:
        raise ValueError("linear_deflection must be a positive finite value")
    angular_degrees = float(angular_deflection_degrees)
    if (
        not math.isfinite(angular_degrees)
        or angular_degrees <= 0.0
        or angular_degrees > 180.0
    ):
        raise ValueError("angular_deflection_degrees must be in (0, 180]")
    if not isinstance(relative, bool):
        raise TypeError("relative must be a bool")

    package, units = read_product_package_translation_units(data)
    root = materialize_definition(package.root_definition)
    solids = _product_solids(root)
    vertex_blocks: list[np.ndarray] = []
    triangle_blocks: list[np.ndarray] = []
    vertex_offset = 0
    angular_radians = math.radians(angular_degrees)
    for solid in solids:
        vertices, triangles = _tessellate_solid(
            solid,
            linear_deflection=linear,
            angular_deflection_radians=angular_radians,
            relative=relative,
        )
        vertex_blocks.append(vertices)
        triangle_blocks.append(triangles + vertex_offset)
        vertex_offset += len(vertices)

    return TessellatedSurfaceMesh(
        vertices=np.concatenate(vertex_blocks, axis=0),
        triangles=np.concatenate(triangle_blocks, axis=0),
        root_definition_id=package.root_definition.definition_id,
        solid_count=len(solids),
        definition_count=len(units),
        linear_deflection=linear,
        angular_deflection_degrees=angular_degrees,
        relative=relative,
    )


__all__ = ["TessellatedSurfaceMesh", "tessellate_product_surface"]
