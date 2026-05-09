"""Rigid assembly constraints with bbox anchors.

Run from the repository root with:
    uv run python examples/04_assembly_constraints.py
"""

import simplecadapi as scad


base = scad.make_box_rsolid(40.0, 20.0, 4.0)
post = scad.make_cylinder_rsolid(3.0, 18.0)
cap = scad.make_box_rsolid(18.0, 10.0, 4.0)

asm = scad.make_assembly_rassembly([
    ("base", base),
    ("post", post),
    ("cap", cap),
])
asm = scad.constrain_offset_rassembly(
    asm, asm.part("base").anchor("bbox.top"), asm.part("post").anchor("bbox.bottom"), 0.0, axis="z"
)
asm = scad.constrain_offset_rassembly(
    asm, asm.part("base").anchor("bbox.center"), asm.part("post").anchor("bbox.center"), 0.0, axis="x"
)
asm = scad.constrain_offset_rassembly(
    asm, asm.part("base").anchor("bbox.center"), asm.part("post").anchor("bbox.center"), 0.0, axis="y"
)
asm = scad.constrain_offset_rassembly(
    asm, asm.part("post").anchor("bbox.top"), asm.part("cap").anchor("bbox.bottom"), 0.0, axis="z"
)
asm = scad.constrain_offset_rassembly(
    asm, asm.part("post").anchor("bbox.center"), asm.part("cap").anchor("bbox.center"), 0.0, axis="x"
)
asm = scad.constrain_offset_rassembly(
    asm, asm.part("post").anchor("bbox.center"), asm.part("cap").anchor("bbox.center"), 0.0, axis="y"
)

result = scad.solve_assembly_rresult(asm)
print("converged", result.report.converged)
print("parts", len(result.part_names()))
for name in result.part_names():
    solid = result.get_solid(name)
    print(name, round(solid.get_volume(), 3))
