"""Profile operations: revolve, loft, and sweep.

Run from the repository root with:
    uv run python examples/05_loft_sweep_revolve.py
"""

from pathlib import Path

import simplecadapi as scad


OUT = Path("examples/out")
OUT.mkdir(parents=True, exist_ok=True)

# Revolve a closed profile into a small knob.
profile = scad.make_polyline_rwire(
    [(0.0, 0.0, 0.0), (4.0, 0.0, 0.0), (3.0, 0.0, 8.0), (1.0, 0.0, 8.0)],
    closed=True,
)
knob = scad.revolve_rsolid(profile, axis=(0.0, 0.0, 1.0), angle=360.0)

# Loft between rectangular sections.
a = scad.make_rectangle_rwire(8.0, 8.0, center=(16.0, 0.0, 0.0))
b = scad.make_rectangle_rwire(4.0, 4.0, center=(16.0, 0.0, 8.0))
loft = scad.loft_rsolid([a, b])

# Sweep a circular face along a polyline path.
profile_face = scad.make_circle_rface((30.0, 0.0, 0.0), 1.0, normal=(1.0, 0.0, 0.0))
path = scad.make_polyline_rwire([(30.0, 0.0, 0.0), (34.0, 0.0, 3.0), (38.0, 3.0, 6.0)])
swept = scad.sweep_rsolid(profile_face, path)

scad.export_step([knob, loft, swept], str(OUT / "profile_operations.step"))
print("knob", round(knob.get_volume(), 3))
print("loft", round(loft.get_volume(), 3))
print("swept", round(swept.get_volume(), 3))
