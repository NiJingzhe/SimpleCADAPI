"""Translate the captured bracket into a SolidWorks automation script."""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad


OUT_DIR = Path(__file__).resolve().parent / "out"
PACKAGE_PATH = OUT_DIR / "ap242_gmsh_bracket.scadpkg"
SCRIPT_PATH = OUT_DIR / "ap242_gmsh_bracket.solidworks.py"
SOLIDWORKS_PATH = OUT_DIR / "ap242_gmsh_bracket.SLDPRT"


def main() -> None:
    if not PACKAGE_PATH.is_file():
        raise FileNotFoundError(f"Run model.py first: {PACKAGE_PATH}")
    script = scad.translator.solidworks_translator.translate_product_package_to_solidworks_script(
        data=PACKAGE_PATH,
        document_name="AP242GmshBracket",
        output_path=str(SOLIDWORKS_PATH),
    )
    SCRIPT_PATH.write_text(script, encoding="utf-8")
    print("solidworks_script", SCRIPT_PATH)
    print("solidworks_output_when_run", SOLIDWORKS_PATH)


if __name__ == "__main__":
    main()
