"""Translate the captured bracket into a Fusion 360 Python script."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path(__file__).resolve().parent / "out"
PACKAGE_PATH = OUT_DIR / "ap242_gmsh_bracket.scadpkg"
SCRIPT_PATH = OUT_DIR / "ap242_gmsh_bracket.fusion360.py"


def main() -> None:
    if not PACKAGE_PATH.is_file():
        raise FileNotFoundError(f"Run model.py first: {PACKAGE_PATH}")
    script = scad.translator.fusion360_translator.translate_product_package_to_fusion360_script(
        data=PACKAGE_PATH,
        document_name="AP242GmshBracket",
    )
    SCRIPT_PATH.write_text(script, encoding="utf-8")
    print("fusion360_script", SCRIPT_PATH)


if __name__ == "__main__":
    main()
