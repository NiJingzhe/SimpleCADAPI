# SDK Surfaces

## Public API groups

- Primitive and sketch construction functions
- Transform, feature, boolean, and export functions
- Functional tagging and selection helpers
- Graph/model serialization and replay entry points
- Expression and semantic reference data types

## Tagging Surface

```python
import simplecadapi as scad

body = scad.make_box_rsolid(10.0, 20.0, 3.0)
scad.apply_tag(body, "role.mounting_plate")
body.auto_tag_faces("box")

top_faces = [face for face in body.get_faces() if "face.top" in scad.list_tags(face)]
print(len(top_faces))
```

Use `apply_tag(shape, tag)` for user-authored semantic tags and `list_tags(shape)` for deterministic inspection. Keep numeric dimensions, measurements, and rich descriptive data in metadata rather than tags.

## Recommended reading order

1. `references/docs/api/README.md`
2. `references/SDK_OVERVIEW.md`
3. `references/V2_MODELING_WORKFLOWS.md`
4. Specific pages under `references/docs/api/`
5. Supporting pages under `references/docs/core/`

## Typical v2 surface

```python
from simplecadapi import GraphSession, export_model_json, replay_model_json

with GraphSession() as session:
    ...

model_json = export_model_json(session)
rebuilt = replay_model_json(model_json)
print(len(rebuilt))
```
