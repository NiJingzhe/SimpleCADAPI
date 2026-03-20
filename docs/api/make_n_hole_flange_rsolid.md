# make_n_hole_flange_rsolid

## API Definition

```python
def make_n_hole_flange_rsolid(flange_outer_diameter = 120.0, flange_inner_diameter = 60.0, flange_thickness = 15.0, boss_outer_diameter = 80.0, boss_height = 5.0, hole_diameter = 8.0, hole_circle_diameter = 100.0, hole_count = 8, chamfer_size = 1.0) -> Solid
```

*Source: evolve.py*

## Description

Create an n-hole flange with a raised boss ring and optional chamfers. The center of the bottom face is placed at the origin.
