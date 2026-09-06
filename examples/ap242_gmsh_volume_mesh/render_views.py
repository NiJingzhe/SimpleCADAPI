"""Render the demo gallery views for ap242_gmsh_volume_mesh.

Views (demo/build.py gallery): isometric, top, and the mount-hole detail.
"""
from pathlib import Path

import simplecadapi as scad

import model

OUT = Path(__file__).resolve().parent / "out"
OUT.mkdir(parents=True, exist_ok=True)

body = model.build_bracket().part.body

views = {
    "render_iso.png": dict(view=(30.0, 45.0), zoom=4.0),
    "render_top.png": dict(view=(90.0, 0.0), zoom=4.0),
    "render_detail.png": dict(view=(25.0, 20.0), zoom=9.0),
}
for name, kw in views.items():
    path = scad.render_screenshot_rpath(
        shapes=body, output_path=str(OUT / name),
        image_size=(1400, 900), show_legend=False, show_callouts=False, **kw)
    print(f"rendered {path}")
