"""Export one durable SimpleCAD part as FCStd, AP242 STEP, and Gmsh MSH."""

from __future__ import annotations
import argparse

from dataclasses import dataclass
import importlib
from pathlib import Path
from typing import Any

import simplecadapi as scad


OUT_DIR = Path(__file__).resolve().parent / "out" / "ap242_gmsh_volume_mesh"
CACHE = scad.CachePolicy(root=OUT_DIR / ".cache")


@dataclass(frozen=True, slots=True)
class GmshMeshReport:
    step_path: Path
    mesh_path: Path
    volume_count: int
    node_count: int
    element_count: int


@scad.part(
    id="ap242_gmsh_bracket",
    revision="1.0.0",
    inputs=(scad.file_input(path="examples/12_ap242_gmsh_volume_mesh.py"),),
    cache=CACHE,
)
def build_bracket() -> scad.Part:
    body = scad.make_box_rsolid(
        width=40.0,
        height=24.0,
        depth=8.0,
        bottom_face_center=(0.0, 0.0, 0.0),
    )
    hole = scad.make_cylinder_rsolid(
        radius=4.0,
        height=12.0,
        bottom_face_center=(-12.0, 0.0, -2.0),
    )
    slot = scad.make_box_rsolid(
        width=14.0,
        height=6.0,
        depth=12.0,
        bottom_face_center=(10.0, 0.0, -2.0),
    )
    body = scad.cut_rsolid(body, hole, slot)
    part = scad.make_part_rpart(
        part_id="ap242_gmsh_bracket",
        body=body,
        name="AP242 Gmsh bracket",
    )
    material = scad.make_material_rmaterial(
        material_id="aluminum_6061_t6",
        name="Aluminum 6061-T6",
        density=2.70e-6,
        density_unit="kg/mm^3",
        color=(0.72, 0.74, 0.78),
    )
    return scad.assign_material_rpart(part, material)


def mesh_step_with_gmsh(
    step_path: str | Path,
    mesh_path: str | Path,
    *,
    mesh_size: float = 2.0,
    gmsh_module: Any | None = None,
) -> GmshMeshReport:
    """Import AP242 STEP with Gmsh's OCC kernel and write a 3D MSH mesh."""

    if mesh_size <= 0.0:
        raise ValueError("mesh_size must be positive")
    source = Path(step_path).expanduser().resolve()
    destination = Path(mesh_path).expanduser().resolve()
    if not source.is_file():
        raise FileNotFoundError(source)
    destination.parent.mkdir(parents=True, exist_ok=True)
    gmsh = gmsh_module
    if gmsh is None:
        try:
            gmsh = importlib.import_module("gmsh")
        except ImportError as exc:
            raise RuntimeError(
                "Gmsh is optional; install it with `pip install simplecadapi[gmsh]`"
            ) from exc

    initialized = False
    try:
        gmsh.initialize()
        initialized = True
        gmsh.model.add(source.stem)
        gmsh.option.setString("Geometry.OCCTargetUnit", "MM")
        imported = gmsh.model.occ.importShapes(str(source))
        gmsh.model.occ.synchronize()
        volumes = gmsh.model.getEntities(3)
        if not volumes:
            raise RuntimeError(
                f"Gmsh imported no 3D volumes from {source}; imported entities: {imported}"
            )
        physical_group = gmsh.model.addPhysicalGroup(
            3,
            [tag for _dimension, tag in volumes],
        )
        gmsh.model.setPhysicalName(3, physical_group, source.stem)
        gmsh.option.setNumber("Mesh.MeshSizeMin", float(mesh_size))
        gmsh.option.setNumber("Mesh.MeshSizeMax", float(mesh_size))
        gmsh.model.mesh.generate(3)
        node_tags, _coordinates, _parameters = gmsh.model.mesh.getNodes()
        _types, element_tags, _node_tags = gmsh.model.mesh.getElements(3)
        element_count = sum(len(tags) for tags in element_tags)
        if not len(node_tags) or not element_count:
            raise RuntimeError("Gmsh generated an empty 3D mesh")
        gmsh.write(str(destination))
    finally:
        if initialized:
            gmsh.finalize()

    if not destination.is_file() or destination.stat().st_size <= 0:
        raise RuntimeError(
            f"Gmsh did not create a non-empty mesh file at {destination}"
        )
    return GmshMeshReport(
        step_path=source,
        mesh_path=destination,
        volume_count=len(volumes),
        node_count=len(node_tags),
        element_count=element_count,
    )


def main(*, generate_mesh: bool = True) -> None:
    result = build_bracket()
    package_path = OUT_DIR / "ap242_gmsh_bracket.scadpkg"
    scad.capture(result, package_path)
    step_path = OUT_DIR / "ap242_gmsh_bracket.step"
    mesh_path = OUT_DIR / "ap242_gmsh_bracket.msh"
    fcstd_path = OUT_DIR / "ap242_gmsh_bracket.FCStd"
    step_report = scad.exporter.export_product_package_to_step(package_path, step_path)
    scad.translator.freecad_translator.translate_product_package_to_fcstd(
        package_path,
        str(fcstd_path),
        document_name="AP242GmshBracket",
    )
    mesh = mesh_step_with_gmsh(step_path, mesh_path) if generate_mesh else None
    print("product_package", package_path)
    print("ap242_step", step_report.output_path)
    print("fcstd", fcstd_path)
    print("ap242_metadata_items", step_report.metadata_item_count)
    if mesh is not None:
        print("gmsh_mesh", mesh.mesh_path)
        print("gmsh_volumes", mesh.volume_count)
        print("gmsh_nodes", mesh.node_count)
        print("gmsh_3d_elements", mesh.element_count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--skip-mesh",
        action="store_true",
        help="Export .scadpkg, AP242 STEP, and FCStd without optional Gmsh meshing.",
    )
    args = parser.parse_args()
    main(generate_mesh=not args.skip_mesh)
