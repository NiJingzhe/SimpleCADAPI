# SDK Surfaces

## Public API groups

- Primitive and sketch construction functions
- Standard parts library modules for reusable mechanical parts
- Transform, feature, boolean, and export functions
- Functional tagging and selection helpers
- Graph/model serialization and replay entry points
- Expression and semantic reference data types

## Standard Parts Surface

```python
import simplecadapi as scad

gear = scad.std.gear.make_spur_gear_rsolid(
    n_teeth=24,
    module=1.5,
    gear_height=8.0,
)
ring = scad.std.gear.make_spur_ring_gear_rsolid(
    n_teeth=72,
    module=1.5,
    gear_height=8.0,
    rim_thickness=4.0,
    backlash=0.08 * 1.5,
)
rack = scad.std.gear.make_spur_rack_rsolid(module=1.5, n_teeth=18)
bearing = scad.std.bearing.make_ball_bearing_rassembly(
    8.0,
    22.0,
    7.0,
    3.5,
)
```

Use standard-library functions first when a task asks for a standard part and does not require complex custom geometry changes. Read `references/docs/stdlib/README.md` for the standard-library index and `references/docs/stdlib/<function_name>.md` for exact signatures.

## Tagging Surface

```python
import simplecadapi as scad

body = scad.make_box_rsolid(width=10.0, height=20.0, depth=3.0)
scad.apply_tag(shape=body, tag="role.mounting_plate")
body.auto_tag_faces("box")

top_faces = [face for face in body.get_faces() if "face.top" in scad.list_tags(shape=face)]
print(len(top_faces))
```

Use `apply_tag(shape=..., tag=...)` for user-authored semantic tags and `list_tags(shape=...)` for deterministic inspection. Keep numeric dimensions, measurements, and rich descriptive data in metadata rather than tags.

## Recommended reading order

1. `references/docs/api/README.md`
2. `references/docs/stdlib/README.md`
3. `references/SDK_OVERVIEW.md`
4. `references/MODELING_WORKFLOWS.md`
5. Specific pages under `references/docs/api/` or `references/docs/stdlib/`
6. Supporting pages under `references/docs/core/`

## Typical replayable surface

```python
from simplecadapi import GraphSession, export_model_json, replay_model_json

with GraphSession() as session:
    ...

model_json = export_model_json(session=session)
rebuilt = replay_model_json(json_str=model_json)
print(len(rebuilt))
```
