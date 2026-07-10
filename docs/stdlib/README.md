# SimpleCAD Standard Library Index

This index includes generated docs for standard part factory functions. Use these functions first when a task needs a standard mechanical part and does not require complex custom geometry changes.

## Import Surfaces

- Recommended package-level module export: `import simplecadapi as scad`, then call functions through submodules such as `scad.std.gear.<function>(...)` and `scad.std.bearing.<function>(...)`.
- Direct submodule import is also supported, for example `from simplecadapi.std.gear import make_spur_gear_rsolid` or `from simplecadapi.std.bearing import make_ball_bearing_rassembly`.

## Usage Guidance

- Prefer standard-library factories for standard bearings, gears, ring gears, and racks before hand-modeling profiles with core geometry APIs.
- Standard parts return normal SimpleCAD shapes or product assemblies, so they can be transformed, tagged, assembled, exported, or combined with core geometry operations.
- Switch to core geometry APIs only when the requested standard part needs substantial custom geometry beyond the factory parameters.

## Bearing Assemblies

- [make_ball_bearing_rassembly](make_ball_bearing_rassembly.md) *(from std/bearing.py)* `stdlib`

## External Gears

- [make_helical_gear_rsolid](make_helical_gear_rsolid.md) *(from std/gear.py)* `stdlib`
- [make_herringbone_gear_rsolid](make_herringbone_gear_rsolid.md) *(from std/gear.py)* `stdlib`
- [make_spur_gear_rsolid](make_spur_gear_rsolid.md) *(from std/gear.py)* `stdlib`

## Internal Ring Gears

- [make_helical_ring_gear_rsolid](make_helical_ring_gear_rsolid.md) *(from std/gear.py)* `stdlib`
- [make_herringbone_ring_gear_rsolid](make_herringbone_ring_gear_rsolid.md) *(from std/gear.py)* `stdlib`
- [make_spur_ring_gear_rsolid](make_spur_ring_gear_rsolid.md) *(from std/gear.py)* `stdlib`

## Cycloidal Reducer Discs

- [make_cycloidal_disc_rsolid](make_cycloidal_disc_rsolid.md) *(from std/gear.py)* `stdlib`

## Racks

- [make_helical_rack_rsolid](make_helical_rack_rsolid.md) *(from std/gear.py)* `stdlib`
- [make_herringbone_rack_rsolid](make_herringbone_rack_rsolid.md) *(from std/gear.py)* `stdlib`
- [make_spur_rack_rsolid](make_spur_rack_rsolid.md) *(from std/gear.py)* `stdlib`
