# make_helical_ring_gear_rsolid

## API Definition

```python
def make_helical_ring_gear_rsolid(n_teeth: int, module: float, pressure_angle: float = 20.0, helix_angle: float = 25.0, gear_height: float = 8.0, rim_thickness: float = 3.0, backlash: float = 0.0, *, addendum_factor: float = 1.0, clearance_factor: float = 0.25) -> Solid
```

*Source: std/gear.py*

## Import Surface

- standard library: `import simplecadapi as scad` then `scad.std.gear.make_helical_ring_gear_rsolid(...)`; direct submodule import: `from simplecadapi.std.gear import make_helical_ring_gear_rsolid`

## Description

Create an internal helical ring gear.

The outer rim is extruded directly. The internal tooth void is built as a
small-step ruled loft through rotated copies of the internal profile, then
subtracted from the rim. Ruled sections avoid smooth loft bulging in STEP
exports while preserving stable section correspondence.

## Parameters

### n_teeth

- **Type**: `int`
- **Description**: Number of internal teeth (>= 3).

### module

- **Type**: `float`
- **Description**: Gear module in mm.

### pressure_angle

- **Type**: `float, default 20`
- **Description**: Pressure angle in degrees.

### helix_angle

- **Type**: `float, default 25`
- **Description**: Helix angle in degrees.

### gear_height

- **Type**: `float, default 8.0`
- **Description**: Ring gear thickness along Z in mm.

### rim_thickness

- **Type**: `float, default 3.0`
- **Description**: Thickness of the rim beyond the tooth roots in mm.

### backlash

- **Type**: `float, default 0.0`
- **Description**: Circumferential tooth-space clearance at the pitch circle in mm.

### addendum_factor

- **Type**: `float, default 1.0`
- **Description**: Internal tooth addendum as a multiple of module.

### clearance_factor

- **Type**: `float, default 0.25`
- **Description**: Internal tooth root clearance beyond the addendum, as a multiple of module.
