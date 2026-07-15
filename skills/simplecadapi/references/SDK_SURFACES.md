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

Use `apply_tag(shape=..., tag=...)` for a local user-authored tag. Use `apply_tag_rselection(...)` when a selector, explicit downward inheritance, or an independent semantic shape view is required. Inspect `local`, `inherited`, `effective`, or `lineage` with `list_tags(shape=..., scope=...)` and `explain_tag(...)`. `effective` excludes lineage. Keep numeric dimensions, measurements, operation events, source roles, and rich descriptive data in typed metadata rather than tags.

## Feature Output Role Surface

The following roles are operation-owned, kernel-proven sets. `one` means exactly
one result is required when the role is requested; `many` means at least one
result is required and all proven results are tagged.

| Operation | Role | Kind | Cardinality | Named tag argument |
| --- | --- | --- | --- | --- |
| Extrude | `extrusion.start` | Face | one | `start_face_tag` |
| Extrude | `extrusion.end` | Face | one | `end_face_tag` |
| Extrude | `extrusion.side` | Face | many | `side_faces_tag` |
| Revolve | `revolution.start` | Face | one | `start_face_tag` |
| Revolve | `revolution.end` | Face | one | `end_face_tag` |
| Revolve | `revolution.side` | Face | many | `side_faces_tag` |
| Fillet | `fillet.patch` | Face | many | `generated_faces_tag` |
| Chamfer | `chamfer.patch` | Face | many | `generated_faces_tag` |
| Shell | `shell.body_face` | Face | many | `body_faces_tag` |
| Shell | `shell.offset_face` | Face | many | `offset_faces_tag` |
| Shell | `shell.closing_descendant` | Face | many | `closing_faces_tag` |
| Shell | `shell.wall` | Edge | many | `wall_edges_tag` |
| Loft | `loft.start` | Face | one | `start_face_tag` |
| Loft | `loft.end` | Face | one | `end_face_tag` |
| Loft | `loft.side` | Face | many | `side_faces_tag` |
| Sweep | `sweep.start` | Face | one | `start_face_tag` |
| Sweep | `sweep.end` | Face | one | `end_face_tag` |
| Sweep | `sweep.side` | Face | many | `side_faces_tag` |

Every feature also accepts `result_tag` for its one result Solid and
`output_tags={"full.role.name": "semantic.tag"}` as the generic role form.
Unknown roles, duplicate named/generic assignments, malformed tags, unavailable
roles, and cardinality mismatches fail the operation. A full revolve has no
separate start/end cap roles. Shell roles vary with actual OCC history and are
not synthesized when unavailable. Sweep rejects profiles with inner wires.

Use `ql.output_role(role_name=...)` to query operation role evidence. Use
`ql.source_binding(binding_id=...)` and `ql.source_topology(topo_id=...)` only for
projected local `TagBinding` evidence.

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
