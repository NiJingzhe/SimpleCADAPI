# make_ball_bearing_rassembly

## API Definition

```python
def make_ball_bearing_rassembly(bore_diameter: float, outer_diameter: float, bearing_width: float, ball_diameter: float, ball_count: Optional[int] = None, raceway_clearance: float = 0.02, edge_chamfer: float = 0.0, assembly_id: str = 'ball_bearing', drive_angle_degrees: Optional[float] = None) -> Assembly
```

*Source: std/bearing.py*

## Import Surface

- standard library: `import simplecadapi as scad` then `scad.std.bearing.make_ball_bearing_rassembly(...)`; direct submodule import: `from simplecadapi.std.bearing import make_ball_bearing_rassembly`

## Description

Create a parameterized radial ball bearing assembly.

This factory returns an `Assembly`, not a merged `Solid`, because a bearing
has useful internal structure.  The returned assembly contains stable
component ids `outer_ring`, `inner_ring`, and `ball_00`, `ball_01`, ... .
The inner and outer rings each carry an `axis` connector, and the assembly
includes one revolute constraint named `inner_outer_revolute` between those
two axes.  Use `bearing.get_component("inner_ring").item.body` to access
the inner-ring geometry directly, or use connector refs such as
`make_connector_ref_rconnectorref("inner_ring", "axis")` when adding shaft
or housing constraints to the same assembly.

The returned bearing assembly also forwards public assembly-level connectors
`inner_axis` and `outer_axis` from `inner_ring.axis` and `outer_ring.axis`.
Parent assemblies can constrain to those connectors without depending on the
bearing's internal component structure. These public axes are offset to the
bearing center plane.

The returned bearing is not grounded. Ground the parent assembly's housing,
shaft, or fixture components explicitly; the standard bearing assembly does
not emit `GroundedJoint` objects that would lock a parent mechanism.

Parameters use explicit SDK-style names rather than compact catalog labels:
`bore_diameter` maps to common `id`, `outer_diameter` maps to `od`,
`bearing_width` maps to axial bearing thickness, `ball_diameter` maps to
ball size, `raceway_clearance` maps to print clearance around the balls, and
`edge_chamfer` maps to edge break/chamfer.  There is intentionally no
Python keyword-only `*` separator in this signature so the function remains
callable with either positional or keyword arguments.

`ball_count=None` lets the factory infer a conservative visual ball count
from the pitch circle.  Explicit `ball_count` is accepted when you need to
match a real bearing or a printed cage design.  Balls are direct sphere
primitive solids, and the inner and outer rings are revolved from arc-groove
profiles to create continuous toroidal raceway grooves.  Balls are visual
rolling elements fixed at their authored positions; the currently modeled
kinematic degree of freedom is only the inner-ring-to-outer-ring revolute
joint.

For printable bearings, the classic checks from many parametric generators
are still useful: `((outer_diameter - bore_diameter) / 2) - ball_diameter`
should leave enough radial wall thickness, and `bearing_width - ball_diameter`
should be positive so balls do not protrude axially.
