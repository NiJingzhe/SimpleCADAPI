# make_naca_propeller_blade_rsolid

## API Definition

```python
def make_naca_propeller_blade_rsolid(blade_length = 5.0, root_chord = 1.5, tip_chord = 0.3, total_twist_angle = 45.0, num_sections = 7, t_c = 0.16) -> Solid
```

*Source: evolve.py*

## Description

Create a single propeller blade solid from a twisted NACA 0016 profile. The blade root starts at the origin and extends along +Z.
