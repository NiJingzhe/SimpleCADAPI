# Modeling Workflows

## Modeling Mental Model

- Model the part as a sequence of intentional operations, not as one opaque final shape.
- Use the standard parts library first when a requested standard component is available and does not need complex custom geometry changes.
- Start from profiles and reference geometry, then create solids with features such as extrude, revolve, loft, and sweep.
- Use booleans and detail features after the base form is clear: cut openings, union intended merged bodies, then apply fillets, chamfers, or shell operations.
- Use `GraphSession` whenever the result should be replayable, inspectable, serialized, or translated.
- Use QL for grounding and selection. Query the facts you need, such as face normals, centers, areas, edge lengths, curve types, and tags.
- Use indexed child-geometry getters such as `get_edges(index)` and `get_faces(index)` when an indexed topology pick is intentional.
- Use semantic tags for design intent and anchors. Keep numeric measurements and geometry facts in metadata or model JSON payloads.
- Treat `export_model_json()` as the interchange boundary for replay and CAD translation.
- Declare directly controlled dimensions with `var(..., unit=..., tolerance=..., tolerance_unit=...)`, and attach derived requirements with `GraphSession.require_tolerance(...)` when manufacturing variation matters.
- Validate incrementally: after each major step, print small QL-derived facts such as selected face count, top face center, edge count, volume, or replay result count.

## 1) Capture a replayable modeling flow

```python
from simplecadapi import GraphSession, export_model_json

with GraphSession() as session:
    ...

payload = export_model_json(session=session)
```

## 2) Import and use in Python

```python
import simplecadapi as scad
from simplecadapi import GraphSession, export_model_json
```

## 3) Keep replay payloads as the interchange boundary

- Prefer `export_model_json()` output instead of hand-written payloads.
- Use `replay_model_json()` when you need deterministic reconstruction.
- Use `import_model_json()` when consuming previously exported payloads.

## 4) Use standard parts when they fit

```python
import simplecadapi as scad

gear = scad.std.gear.make_spur_gear_rsolid(
    n_teeth=24,
    module=1.5,
    gear_height=8.0,
)
rack = scad.std.gear.make_spur_rack_rsolid(module=1.5, n_teeth=18)
bearing = scad.std.bearing.make_ball_bearing_rassembly(
    8.0,
    22.0,
    7.0,
    3.5,
)
```

- Read `references/docs/stdlib/README.md` before hand-modeling a standard mechanical part.
- Use `references/docs/stdlib/<function_name>.md` for exact standard-library signatures.
- Continue with core geometry APIs when the standard part requires substantial custom geometry beyond the provided parameters.

## 5) QL-grounded feature workflow

```python
import simplecadapi as scad
from simplecadapi import ql

with scad.GraphSession() as session:
    profile = scad.make_circle_rface(center=(0, 0, 0), radius=1.0)
    body = scad.extrude_rsolid(
        profile=profile,
        direction=(0, 0, 1),
        distance=4.0,
        end_face_tag="role.sweep_profile",
        result_tag="part.body",
    )
    end_face = (
        ql.faces()
        .where(ql.output_role(role_name="extrusion.end"))
        .exactly(1)
        .resolve(body)[0]
    )
    print("end face center", end_face.get_center())
    path = scad.make_segment_rwire(start=(0, 0, 4), end=(0, 0, 8))
    swept = scad.sweep_rsolid(profile=end_face, path=path)

payload = scad.export_model_json(session=session)
rebuilt = scad.replay_model_json(json_str=payload)
print("rebuilt", len(rebuilt))
```

## 6) Selection and tag discipline

- Prefer QL selectors for semantic/geometric feature input selection.
- Use `get_edges(index)`, `get_faces(index)`, `get_wires(index)`, or `get_vertices(index)` for intentional indexed picks in examples.
- Attach local semantic tags with `apply_tag(shape=..., tag=...)`. Use `apply_tag_rselection(...)` for selector targets, explicit downward inheritance, or immutable semantic branches.
- Inspect with `list_tags(shape=..., scope=...)` and `explain_tag(...)`; `effective` excludes `lineage`.
- Use tags for intent, roles, anchors, groups, and topology names.
- Store dimensions, positions, measured geometry, operation events, source roles, and descriptive payloads in metadata or model JSON, not in tags.
- Keep QL result prints concise: selected count, centers, normals, areas, lengths, or tags.

## 7) Kernel-proven feature output roles

- Feature output roles are typed tracking evidence, not user tag strings. Query them with `ql.output_role(role_name=...)`.
- The feature APIs accept named tag arguments and a generic `output_tags={role: tag}` mapping. Every requested role is strict: `one` roles require exactly one proven target, and `many` roles require at least one and tag the full proven set.
- Generic and named forms cannot assign the same role in one call. Unknown roles and non-normalized tags fail before returning geometry.
- `result_tag` targets the one result Solid. Role tags target Faces except for `shell.wall`, which targets Edges.
- A 360-degree revolve has no distinct start/end caps. Requesting those tags fails rather than inventing cap roles.
- Shell role availability follows actual OCC evidence. For example, an operation may prove offset faces, closing descendants, and wall edges without proving a `shell.body_face` set.
- Sweep currently rejects a profile with inner wires rather than silently sweeping only its outer wire.

```python
body = scad.extrude_rsolid(
    profile=profile,
    direction=(0, 0, 1),
    distance=10.0,
    start_face_tag="anchor.base",
    end_face_tag="role.mounting_surface",
    side_faces_tag="group.outer_walls",
    result_tag="part.body",
)

mounting_face = (
    ql.faces()
    .where(ql.output_role(role_name="extrusion.end"))
    .exactly(1)
    .resolve(body)[0]
)
print(scad.list_tags(shape=mounting_face, scope="local"))
```

In a `GraphSession`, each requested assignment becomes a canonical
`apply_tag_rselection` semantic node. The feature node remains geometry-only, and
replay validates both the recomputed role set and the exact selected refs.

## 8) Replay-safe source projection

When a feature supports source projection, keep the returned semantic view in the
feature's input chain:

```python
profile = scad.make_rectangle_rface(width=5.0, height=3.0)
source_edge = profile.get_edges(0)
profile = scad.apply_tag_rselection(
    scope=profile,
    targets=[source_edge],
    tag="role.source_edge",
)
source_edge = scad.select_edges_by_tag(
    shape=profile,
    tag="role.source_edge",
    scope="local",
)[0]
source_binding_id = scad.explain_tag(
    shape=source_edge,
    tag="role.source_edge",
    scope="local",
)[0]["binding_id"]

body = scad.extrude_rsolid(
    profile=profile,
    direction=(0, 0, 1),
    distance=2.0,
)
projected_face = (
    ql.faces()
    .where(ql.source_binding(binding_id=source_binding_id))
    .exactly(1)
    .resolve(body)[0]
)
print(scad.list_tags(shape=projected_face, scope="local"))
```

The projected binding preserves the exact source binding ID, source topology ID,
target topology ID, operation, role, and evidence method. `ql.source_binding(...)`
and `ql.source_topology(...)` inspect this local evidence. They do not search tag
text or infer ancestry from geometry. Calling `apply_tag_rselection(...)` but then
passing the original profile to the feature creates a detached semantic branch and
does not authorize hidden coupling.

## 9) Boolean and body discipline

- Use `union_rsolid(...)` when multiple solids should become one integrated body.
- Ensure bodies that should union into one solid have real geometric overlap or embedding.
- Use `cut_rsolid(...)` for subtractive features and `intersect_rsolid(...)` for common-volume workflows.
- Validate body count and volume after major boolean operations.

## 8) Dimension tolerance chains

```python
width = scad.var("width", 10.0, unit="mm", tolerance=0.1)
gap = scad.var("gap", 0.5, unit="mm", tolerance=(-0.05, 0.1))
overall = width + gap

with scad.GraphSession() as session:
    body = scad.make_box_rsolid(width, 2.0, 1.0)
    session.require_tolerance(overall, (-0.15, 0.2), tolerance_unit="mm", name="overall")

report = session.validate_tolerances(raise_on_failure=True)
```

- Use `worst_case` for a guaranteed conservative envelope.
- Use `rss` only when distinct source dimensions can be treated as independent.
- Every source variable in a chain must have a declared tolerance.
- Unit-aware expressions infer dimensions automatically and cannot mix legacy
  variables without units.
- Length and angle use canonical `mm` and `deg` values in CAD operations.
- Read `references/docs/core/physical-units.md` for unit and inference rules.
- Read `references/docs/core/dimension-tolerance-chains.md` for complete rules.
