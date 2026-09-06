"""Export the captured bracket directly from evaluated BREP as triangle OBJ."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path(__file__).resolve().parent / "out"
PACKAGE_PATH = OUT_DIR / "ap242_gmsh_bracket.scadpkg"
OBJ_PATH = OUT_DIR / "ap242_gmsh_bracket.obj"


def main() -> None:
    if not PACKAGE_PATH.is_file():
        raise FileNotFoundError(f"Run model.py first: {PACKAGE_PATH}")
    report = scad.exporter.export_product_package_to_obj(
        data=PACKAGE_PATH,
        output_path=OBJ_PATH,
        linear_deflection=0.05,
        angular_deflection_degrees=10.0,
    )
    print("obj", report.output_path)
    print("obj_vertices", report.vertex_count)
    print("obj_triangles", report.triangle_count)
    print("tessellation_backend", report.tessellation_backend)
    print("linear_deflection", report.linear_deflection)
    print("angular_deflection_degrees", report.angular_deflection_degrees)


if __name__ == "__main__":
    main()
