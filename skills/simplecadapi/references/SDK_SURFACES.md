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
| Box | `box.bottom` | Face | one | `bottom_face_tag` |
| Box | `box.top` | Face | one | `top_face_tag` |
| Box | `box.front` | Face | one | `front_face_tag` |
| Box | `box.back` | Face | one | `back_face_tag` |
| Box | `box.left` | Face | one | `left_face_tag` |
| Box | `box.right` | Face | one | `right_face_tag` |
| Cone | `cone.start` | Face | one | `start_face_tag` |
| Cone | `cone.end` | Face | one | `end_face_tag` |
| Cone | `cone.side` | Face | one | `side_face_tag` |
| Cone | `cone.start_boundary` | Edge | one | `start_edge_tag` |
| Cone | `cone.end_boundary` | Edge | one | `end_edge_tag` |
| Cone | `cone.seam` | Edge | one | `seam_edge_tag` |
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
| Twisted sweep | `twisted_sweep.start` | Face | one | `start_face_tag` |
| Twisted sweep | `twisted_sweep.end` | Face | one | `end_face_tag` |
| Twisted sweep | `twisted_sweep.side` | Face | many | `side_faces_tag` |

Every feature also accepts `result_tag` for its one result Solid. Each output
role has one semantic tag argument named for the target, such as
`start_face_tag`, `side_faces_tag`, or `generated_faces_tag`; there is no generic
role-to-tag mapping. Malformed tags, unavailable roles, and cardinality
mismatches fail the operation. A full revolve has no
separate start/end cap roles. Shell roles vary with actual OCC history and are
not synthesized when unavailable. Box Edge roles are unsupported because the
kernel builder has no equivalent direct Edge witnesses. Sweep and twisted sweep
reject profiles with inner wires. A pointed cone has no `cone.end` cap Face, but its
`cone.end_boundary` remains the kernel-proven degenerate apex Edge.

Use `ql.output_role(role_name=...)` to query operation role evidence. Use
`ql.source_binding(binding_id=...)` and `ql.source_topology(topo_id=...)` only for
projected local `TagBinding` evidence.

## Unified Tag Contract

Topology identity and user semantics use the same `TagBinding` and public query
surfaces. The authoring path and evidence determine projection behavior, not the
tag text:

- `tag_prefix="housing"` creates topology-identity tags such as
  `housing.face.top` and `housing.solid`. These bindings carry `topology_name`
  evidence and identify kernel-proven result topology.
- `top_face_tag="role.cover"` attaches `role.cover` to the kernel-proven top
  Face. Its binding carries operation output role evidence.
- `result_tag="part.housing"` attaches `part.housing` to the returned Solid.
  Its binding carries operation result evidence.

All three are discoverable with `list_tags(...)` and `explain_tag(...)` and
queryable with `ql.tag(...)`. A topology object may carry all three. Only a
topology-identity binding projects through the stricter exact-correspondence
path; a tag string does not opt into that behavior by resembling a topology tag.

## Constrained Sketch Tag Surface

Sketch entity IDs are creation-time local identifiers. When a constrained
profile is promoted, the exact ordered promotion map creates topology-identity
`TagBinding`s with `topology_name` evidence:

- Profile `bottom` in sketch `rect`: `sketch.rect.profile.bottom` on the Face or Wire.
- Entity `right` in sketch `rect`: `sketch.rect.entity.right` on its promoted Edge.

The promotion path validates that the generated Edge count equals the entity
map before attaching tags. It does not use geometric similarity, area,
normal, position, or enumeration order to repair a mismatch. Compatibility
tags such as `sketch_entity.right` remain ordinary compatibility tags.
Downstream features project topology-identity bindings only when kernel history
proves exact source-to-target correspondence.

## Recommended reading order

1. `references/docs/api/README.md`
2. `references/docs/stdlib/README.md`
3. `references/SDK_OVERVIEW.md`
4. `references/MODELING_WORKFLOWS.md`
5. Specific pages under `references/docs/api/` or `references/docs/stdlib/`
6. Supporting pages under `references/docs/core/`

## Typical replayable surface

```python
import simplecadapi as scad

@scad.model(graph_id="demo")
def build_model():
    result = ...
    scad.capture_result(value=result)
    return result

model = build_model()
model_json = model.model_json
rebuilt = model.replay()
print(len(rebuilt))
```
