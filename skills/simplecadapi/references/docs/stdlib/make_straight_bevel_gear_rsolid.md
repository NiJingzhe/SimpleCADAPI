# make_straight_bevel_gear_rsolid

## API Definition

```python
def make_straight_bevel_gear_rsolid(n_teeth: int, module: float, pitch_angle: float = 45.0, pressure_angle: float = 20.0, face_width: float = 8.0, *, addendum_factor: float = 1.0, clearance_factor: float = 0.25, backlash: float = 0.0) -> Solid
```

*Source: std/gear.py*

## Import Surface

- standard library: `import simplecadapi as scad` then `scad.std.gear.make_straight_bevel_gear_rsolid(...)`; direct submodule import: `from simplecadapi.std.gear import make_straight_bevel_gear_rsolid`

## Description

Create a straight bevel gear with standard metric tooth proportions. The large-end transverse section uses an analytic involute profile. A similar small-end section is placed on the pitch cone and connected with ruled straight tooth surfaces.

The returned solid contains nominal tooth geometry. Releasing a mating pair still requires mounting-distance, contact-pattern, backlash, material, heat-treatment, and strength checks.

## Parameters

- `n_teeth`: Number of teeth, at least 3.
- `module`: Large-end transverse module in millimetres.
- `pitch_angle`: Pitch-cone angle in degrees, greater than 0 and less than 90.
- `pressure_angle`: Transverse pressure angle in degrees.
- `face_width`: Tooth face width along the pitch-cone generator in millimetres; must be smaller than the outer pitch-cone distance.
- `addendum_factor`: Large-end tooth addendum divided by module.
- `clearance_factor`: Root clearance beyond the addendum divided by module.
- `backlash`: Large-end circumferential tooth-thickness reduction at the pitch circle in millimetres.
