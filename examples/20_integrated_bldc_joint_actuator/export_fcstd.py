"""Export the integrated BLDC actuator product package as FreeCAD FCStd."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path("examples/out/integrated_bldc_joint_actuator")
PACKAGE_PATH = OUT_DIR / "integrated_bldc_joint_actuator.scadpkg"
FCSTD_PATH = OUT_DIR / "integrated_bldc_joint_actuator.FCStd"


def main() -> None:
    """Translate the captured `.scadpkg` into a replayable FreeCAD document."""

    if not PACKAGE_PATH.is_file():
        raise FileNotFoundError(f"Run main.py first: {PACKAGE_PATH}")
    scad.translator.freecad_translator.translate_product_package_to_fcstd(
        PACKAGE_PATH,
        str(FCSTD_PATH),
        document_name="IntegratedBLDCJointActuator",
    )
    print("fcstd", FCSTD_PATH)
    print("fcstd_bytes", FCSTD_PATH.stat().st_size)


if __name__ == "__main__":
    main()
