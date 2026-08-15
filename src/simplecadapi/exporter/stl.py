"""Quad-dominant STL export for validated product packages."""

from __future__ import annotations

from dataclasses import dataclass
import importlib
from pathlib import Path
import tempfile
from typing import Any

from OCP.BRepTools import BRepTools

from ..artifacts.assembly_io import materialize_definition
from ..operations import make_compound_from_assembly_rcompound
from ..product import Assembly, Part
from ..translator.package_units import (
    ProductPackageInput,
    read_product_package_translation_units,
)


@dataclass(frozen=True, slots=True)
class ProductSTLExportReport:
    """Evidence from quad-dominant product-surface remeshing and STL export."""

    output_path: Path
    root_definition_id: str
    solid_count: int
    definition_count: int
    quadrilateral_count: int
    residual_triangle_count: int
    stl_triangle_count: int
    quad_fraction: float
    mesh_size: float
    remesh_backend: str = "gmsh-quad-dominant"


def _load_gmsh() -> Any:
    try:
        return importlib.import_module("gmsh")
    except ImportError as exc:
        raise RuntimeError(
            "Product STL export requires the 'gmsh' optional dependency; "
            "install simplecadapi[gmsh]"
        ) from exc


def _product_shape(value: Part | Assembly):
    if isinstance(value, Part):
        return value.body.wrapped, 1
    projection = make_compound_from_assembly_rcompound(assembly=value)
    solid_count = int(
        projection.get_metadata("assembly_projection", {}).get("solid_count", 0)
    )
    if solid_count <= 0:
        raise ValueError("Product assembly produced no solids for STL export")
    return projection.wrapped, solid_count


def _surface_element_counts(gmsh: Any) -> tuple[int, int, int]:
    quadrilaterals = 0
    triangles = 0
    stl_triangles = 0
    element_types, element_tags, _node_tags = gmsh.model.mesh.getElements(2)
    for element_type, tags in zip(element_types, element_tags):
        name, dimension, _order, node_count, _coords, primary_node_count = (
            gmsh.model.mesh.getElementProperties(element_type)
        )
        if int(dimension) != 2:
            continue
        count = len(tags)
        if int(primary_node_count) == 4 and "Quadrilateral" in str(name):
            quadrilaterals += count
            stl_triangles += 2 * count
        elif int(primary_node_count) == 3 and "Triangle" in str(name):
            triangles += count
            stl_triangles += count
        else:
            raise RuntimeError(
                f"Gmsh produced unsupported STL surface element {name!r} "
                f"with {node_count} nodes"
            )
    return quadrilaterals, triangles, stl_triangles


def export_product_package_to_stl(
    data: ProductPackageInput,
    output_path: str | Path,
    *,
    mesh_size: float = 1.0,
    recombination_angle_degrees: float = 45.0,
) -> ProductSTLExportReport:
    """Export one validated `.scadpkg` as a quad-dominant remeshed STL.

    Gmsh recombines each CAD surface into quadrilaterals before its STL writer
    splits every quad into two triangles, as required by the STL file format.
    """

    size = float(mesh_size)
    if size <= 0.0:
        raise ValueError("mesh_size must be greater than zero")
    angle = float(recombination_angle_degrees)
    if not 0.0 < angle <= 180.0:
        raise ValueError("recombination_angle_degrees must be in (0, 180]")

    package, units = read_product_package_translation_units(data)
    root = materialize_definition(package.root_definition)
    shape, solid_count = _product_shape(root)
    destination = Path(output_path).expanduser().resolve()
    if destination.suffix.lower() != ".stl":
        raise ValueError("output_path must end in .stl")
    destination.parent.mkdir(parents=True, exist_ok=True)

    gmsh = _load_gmsh()
    initialized = False
    with tempfile.TemporaryDirectory(prefix="simplecad_product_stl_") as temp_dir:
        brep_path = Path(temp_dir) / "product.brep"
        if not BRepTools.Write_s(shape, str(brep_path)):
            raise RuntimeError(
                "OpenCASCADE failed to serialize product BREP for remeshing"
            )
        try:
            gmsh.initialize()
            initialized = True
            gmsh.option.setNumber("General.Terminal", 0)
            gmsh.model.add("SimpleCADProductSTL")
            imported = gmsh.model.occ.importShapes(
                str(brep_path), highestDimOnly=True, format="brep"
            )
            if not imported:
                raise RuntimeError("Gmsh imported no product geometry")
            gmsh.model.occ.synchronize()
            surfaces = gmsh.model.getEntities(2)
            if not surfaces:
                raise RuntimeError("Gmsh product geometry has no meshable surfaces")
            gmsh.option.setNumber("Mesh.Algorithm", 8)
            gmsh.option.setNumber("Mesh.RecombinationAlgorithm", 1)
            gmsh.option.setNumber("Mesh.MeshSizeMin", size)
            gmsh.option.setNumber("Mesh.MeshSizeMax", size)
            for _dimension, tag in surfaces:
                gmsh.model.mesh.setRecombine(2, tag, angle)
            gmsh.model.mesh.generate(2)
            quadrilaterals, triangles, stl_triangles = _surface_element_counts(gmsh)
            if quadrilaterals + triangles == 0:
                raise RuntimeError("Gmsh produced no surface elements")
            gmsh.write(str(destination))
        finally:
            if initialized:
                gmsh.finalize()

    if not destination.is_file() or destination.stat().st_size <= 0:
        raise RuntimeError("Gmsh did not create a non-empty STL file")
    surface_count = quadrilaterals + triangles
    return ProductSTLExportReport(
        output_path=destination,
        root_definition_id=package.root_definition.definition_id,
        solid_count=solid_count,
        definition_count=len(units),
        quadrilateral_count=quadrilaterals,
        residual_triangle_count=triangles,
        stl_triangle_count=stl_triangles,
        quad_fraction=quadrilaterals / surface_count,
        mesh_size=size,
    )


__all__ = ["ProductSTLExportReport", "export_product_package_to_stl"]
