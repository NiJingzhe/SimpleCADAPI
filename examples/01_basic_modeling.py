"""Basic shape-first modeling with the 1.x-style functional API.

Run from the repository root with:
    uv run python examples/01_basic_modeling.py
"""

from pathlib import Path

import simplecadapi as scad


OUT = Path("examples/out")
OUT.mkdir(parents=True, exist_ok=True)


base = scad.make_box_rsolid(60.0, 36.0, 8.0, bottom_face_center=(0.0, 0.0, 0.0))
hole = scad.make_cylinder_rsolid(5.0, 14.0, bottom_face_center=(0.0, 0.0, -3.0))
slot = scad.make_box_rsolid(18.0, 8.0, 14.0, bottom_face_center=(14.0, 0.0, -3.0))
part = scad.cut_rsolidlist(base, hole, slot)

boss = scad.make_cylinder_rsolid(8.0, 7.0, bottom_face_center=(-18.0, 0.0, 8.0))
part = scad.union_rsolid(part, boss)
part.auto_tag_faces("box")

print("volume", round(part.get_volume(), 3))
print("faces", len(part.get_faces()))
print("edges", len(part.get_edges()))

scad.export_step(part, str(OUT / "basic_modeling.step"))
scad.export_stl(part, str(OUT / "basic_modeling.stl"))
print("wrote", OUT / "basic_modeling.step")
