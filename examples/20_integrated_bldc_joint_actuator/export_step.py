"""Export the integrated BLDC actuator product package as AP242 STEP."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path("examples/out/integrated_bldc_joint_actuator")
PACKAGE_PATH = OUT_DIR / "integrated_bldc_joint_actuator.scadpkg"
STEP_PATH = OUT_DIR / "integrated_bldc_joint_actuator.step"


def main() -> None:
    """Translate the captured `.scadpkg` into one AP242 STEP assembly."""

    if not PACKAGE_PATH.is_file():
        raise FileNotFoundError(f"Run main.py first: {PACKAGE_PATH}")
    report = scad.exporter.export_product_package_to_step(PACKAGE_PATH, STEP_PATH)
    print("step", report.output_path)
    print("step_definitions", len(report.definition_ids))
    print("step_occurrences", report.occurrence_count)
    print("step_bytes", STEP_PATH.stat().st_size)


if __name__ == "__main__":
    main()
