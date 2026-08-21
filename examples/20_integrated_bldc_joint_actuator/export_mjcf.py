"""Export the integrated BLDC actuator product package as MuJoCo MJCF."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path("examples/out/integrated_bldc_joint_actuator")
PACKAGE_PATH = OUT_DIR / "integrated_bldc_joint_actuator.scadpkg"
MJCF_PATH = OUT_DIR / "integrated_bldc_joint_actuator.xml"
MAPPING_PATH = OUT_DIR / "integrated_bldc_joint_actuator.mapping.json"
MESH_DIR = OUT_DIR / "integrated_bldc_joint_actuator_meshes"
DEFAULT_DENSITY_KG_M3 = 7850.0


def main() -> None:
    """Compile the captured .scadpkg into an MJCF model with mapping."""

    if not PACKAGE_PATH.is_file():
        raise FileNotFoundError(f"Run main.py first: {PACKAGE_PATH}")
    report = scad.exporter.export_product_package_to_mjcf(
        data=PACKAGE_PATH,
        output_path=MJCF_PATH,
        mapping_path=MAPPING_PATH,
        mesh_directory=MESH_DIR,
        linear_deflection=0.15,
        default_density_kg_m3=DEFAULT_DENSITY_KG_M3,
    )
    print("mjcf", report.output_path)
    print("mjcf_mapping", report.mapping_path)
    print("mjcf_meshes", report.mesh_directory)
    print("mjcf_bodies", report.body_count)
    print("mjcf_joints", report.joint_count)
    print("mjcf_equalities", report.equality_count)
    print("mjcf_sites", report.site_count)
    print("mjcf_mesh_count", report.mesh_count)
    print("mjcf_default_density_parts", report.default_density_count)


if __name__ == "__main__":
    main()
