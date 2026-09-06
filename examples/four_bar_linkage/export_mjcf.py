"""Export the four-bar linkage product package as MuJoCo MJCF."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad

OUT_DIR = Path(__file__).resolve().parent / "out"
PACKAGE_PATH = OUT_DIR / "four_bar_linkage.scadpkg"
MJCF_PATH = OUT_DIR / "four_bar_linkage.xml"
MAPPING_PATH = OUT_DIR / "four_bar_linkage.mapping.json"
MESH_DIR = OUT_DIR / "four_bar_linkage_meshes"


def main() -> None:
    """Compile the captured `.scadpkg` into an MJCF model."""

    if not PACKAGE_PATH.is_file():
        raise FileNotFoundError(f"Run main.py first: {PACKAGE_PATH}")
    report = scad.exporter.export_product_package_to_mjcf(
        data=PACKAGE_PATH,
        output_path=MJCF_PATH,
        mapping_path=MAPPING_PATH,
        mesh_directory=MESH_DIR,
        linear_deflection=0.1,
    )
    print("mjcf", report.output_path)
    print("mjcf_bodies", report.body_count)
    print("mjcf_joints", report.joint_count)
    print("mjcf_equalities", report.equality_count)
    print("mjcf_closures", report.closure_count)

if __name__ == "__main__":
    main()
