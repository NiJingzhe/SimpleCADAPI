"""Export the compact reducer product package as MuJoCo MJCF."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path(__file__).resolve().parent / "out"
PACKAGE_PATH = OUT_DIR / "compact_two_stage_planetary_reducer.scadpkg"
MJCF_PATH = OUT_DIR / "compact_two_stage_planetary_reducer.xml"
MAPPING_PATH = OUT_DIR / "compact_two_stage_planetary_reducer.mapping.json"
MESH_DIR = OUT_DIR / "compact_two_stage_planetary_reducer_meshes"
BEARING_STEEL_DENSITY_KG_M3 = 7850.0


def main() -> None:
    if not PACKAGE_PATH.is_file():
        raise FileNotFoundError(f"Run main.py first: {PACKAGE_PATH}")
    report = scad.exporter.export_product_package_to_mjcf(
        data=PACKAGE_PATH,
        output_path=MJCF_PATH,
        mapping_path=MAPPING_PATH,
        mesh_directory=MESH_DIR,
        linear_deflection=0.15,
        default_density_kg_m3=BEARING_STEEL_DENSITY_KG_M3,
    )
    print("mjcf", report.output_path)
    print("mjcf_mapping", report.mapping_path)
    print("mjcf_meshes", report.mesh_directory)
    print("mjcf_bodies", report.body_count)
    print("mjcf_joints", report.joint_count)
    print("mjcf_equalities", report.equality_count)
    print("mjcf_sites", report.site_count)
    print("mjcf_default_density_parts", report.default_density_count)


if __name__ == "__main__":
    main()
