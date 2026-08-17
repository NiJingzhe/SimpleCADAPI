"""Translate the captured bracket into a standalone FreeCAD Python script."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path(__file__).resolve().parents[1] / "out" / "ap242_gmsh_volume_mesh"
PACKAGE_PATH = OUT_DIR / "ap242_gmsh_bracket.scadpkg"
SCRIPT_PATH = OUT_DIR / "ap242_gmsh_bracket.freecad.py"


def main() -> None:
    if not PACKAGE_PATH.is_file():
        raise FileNotFoundError(f"Run model.py first: {PACKAGE_PATH}")
    script = (
        scad.translator.freecad_translator.translate_product_package_to_freecad_script(
            data=PACKAGE_PATH,
            document_name="AP242GmshBracket",
        )
    )
    SCRIPT_PATH.write_text(script, encoding="utf-8")
    print("freecad_script", SCRIPT_PATH)


if __name__ == "__main__":
    main()
