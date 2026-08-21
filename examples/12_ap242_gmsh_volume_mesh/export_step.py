"""Export the captured bracket product package as an AP242 STEP file."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path(__file__).resolve().parents[1] / "out" / "ap242_gmsh_volume_mesh"
PACKAGE_PATH = OUT_DIR / "ap242_gmsh_bracket.scadpkg"
STEP_PATH = OUT_DIR / "ap242_gmsh_bracket.step"


def main() -> None:
    if not PACKAGE_PATH.is_file():
        raise FileNotFoundError(f"Run model.py first: {PACKAGE_PATH}")
    report = scad.exporter.export_product_package_to_step(
        data=PACKAGE_PATH,
        output_path=STEP_PATH,
    )
    print("ap242_step", report.output_path)
    print("ap242_metadata_items", report.metadata_item_count)


if __name__ == "__main__":
    main()
