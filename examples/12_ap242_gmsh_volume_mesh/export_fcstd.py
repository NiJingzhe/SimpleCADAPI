"""Translate the captured bracket product package to editable FreeCAD FCStd."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path(__file__).resolve().parents[1] / "out" / "ap242_gmsh_volume_mesh"
PACKAGE_PATH = OUT_DIR / "ap242_gmsh_bracket.scadpkg"
FCSTD_PATH = OUT_DIR / "ap242_gmsh_bracket.FCStd"


def main() -> None:
    if not PACKAGE_PATH.is_file():
        raise FileNotFoundError(f"Run model.py first: {PACKAGE_PATH}")
    output = scad.translator.freecad_translator.translate_product_package_to_fcstd(
        data=PACKAGE_PATH,
        output_path=str(FCSTD_PATH),
        document_name="AP242GmshBracket",
    )
    print("fcstd", output)


if __name__ == "__main__":
    main()
