"""S3 render helper: produce the four named demo views from the delivered package.

Views (visual contract planned by Role 3):
  render_iso.png    (35, 45)   isometric overview of the whole bracket
  render_front.png  (0, 90)    orthographic front (looking -Y): L profile + ribs
  render_top.png    (90, 0)    orthographic top: shelf footprint + load hole
  render_detail.png (30, 120)  close-up: gusset rib + mount hole zone
Renders read the captured package (materialized in a fresh process), so the
pictures show the delivered artifact, not an in-memory rebuild.
"""

from __future__ import annotations

from pathlib import Path

import simplecadapi as scad

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE.parents[1] / "out"
PACKAGE_PATH = OUT_DIR / "ap242_gmsh_bracket.scadpkg"

VIEWS = {
    "render_iso.png": {"view": (35.0, 45.0)},
    "render_front.png": {"view": (0.0, 90.0)},
    "render_top.png": {"view": (90.0, 0.0)},
    "render_detail.png": {"view": (30.0, 120.0), "zoom": 2.4},
}


def main() -> None:
    package = scad.read_product_package(PACKAGE_PATH)
    scad.validate_product_package(package)
    part = scad.materialize_definition(package.root_definition)
    body = part.body
    for name, options in VIEWS.items():
        output_path = OUT_DIR / name
        scad.render_screenshot_rpath(
            shapes=body,
            output_path=str(output_path),
            image_size=(1400, 900),
            show_axes=True,
            show_legend=False,
            show_callouts=False,
            **options,
        )
        size = output_path.stat().st_size if output_path.exists() else 0
        print(f"render {name} {size} bytes view={options['view']}")


if __name__ == "__main__":
    main()
