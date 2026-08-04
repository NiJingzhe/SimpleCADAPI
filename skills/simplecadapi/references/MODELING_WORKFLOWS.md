# Modeling Workflows

## Modeling Mental Model

- Follow the Coding Standard in `SKILL.md`: one part per file, one assembly file, parameters colocated with the file that uses them, and every exposed tunable parameter declared with `var()`/`Var`.
- Model the part as a sequence of intentional operations, not as one opaque final shape.
- Use the standard parts library first when a requested standard component is available and does not need complex custom geometry changes.
- Start from profiles and reference geometry, then create solids with features such as extrude, revolve, loft, and sweep.
- Use booleans and detail features after the base form is clear: cut openings, union intended merged bodies, then apply fillets, chamfers, or shell operations.
- Use `@scad.model` for a top-level replayable entry point. It owns one `GraphSession` and returns a `ModelResult`; use `@scad.requires_session` for child builders.
- Use QL for grounding and selection. Query the facts you need, such as face normals, centers, areas, edge lengths, curve types, and tags.
- Use indexed child-geometry getters such as `get_edges(index)` and `get_faces(index)` when an indexed topology pick is intentional.
- Use semantic tags for design intent and anchors. Keep numeric measurements and geometry facts in metadata or model JSON payloads.
- Treat `ModelResult.model_json` as the interchange boundary for new model entry points. Use `export_model_json(session=...)` for lower-level direct sessions.
- Validate incrementally: after each major step, print small QL-derived facts such as selected face count, top face center, edge count, volume, or replay result count.

## 1) Capture a replayable modeling flow

```python
import simplecadapi as scad

@scad.model(graph_id="bracket")
def build_bracket():
    body = scad.make_box_rsolid(width=20.0, height=10.0, depth=3.0)
    scad.capture_result(value=body)
    return body

result = build_bracket()
payload = result.model_json
rebuilt = result.replay()
```

## 2) Import and use in Python

```python
import simplecadapi as scad
```

## 3) Keep replay payloads as the interchange boundary

- Prefer `export_model_json()` output instead of hand-written payloads.
- Use `ModelResult.replay()` for a model invocation, or `replay_model_json(json_str=...)` when consuming standalone model JSON.
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
    bore_diameter=8.0,
    outer_diameter=22.0,
    bearing_width=7.0,
    ball_diameter=3.5,
)
```

- Read `references/docs/stdlib/README.md` before hand-modeling a standard mechanical part.
- Use `references/docs/stdlib/<function_name>.md` for exact standard-library signatures.
- Continue with core geometry APIs when the standard part requires substantial custom geometry beyond the provided parameters.

## 5) QL-grounded feature workflow

```python
import simplecadapi as scad
from simplecadapi import ql

@scad.model(graph_id="swept_profile")
def build_model():
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
    scad.capture_result(value=swept)
    return swept

result = build_model()
rebuilt = result.replay()
print("rebuilt", len(rebuilt))
```

## 6) Selection and tag discipline

- Prefer QL selectors for semantic/geometric feature input selection.
- Use `get_edges(index)`, `get_faces(index)`, `get_wires(index)`, or `get_vertices(index)` for intentional indexed picks in examples.
- Attach semantic tags with `apply_tag(shape=..., tag=...)` and inspect with `list_tags(shape=...)`.
- Use tags for topology identity, intent, roles, anchors, and groups.
- Store dimensions, positions, measured geometry, and descriptive payloads in metadata or model JSON, not in tags.
- Keep QL result prints concise: selected count, centers, normals, areas, lengths, or tags.

## 7) Boolean and body discipline

- Use `union_rsolid(...)` when multiple solids should become one integrated body.
- Ensure bodies that should union into one solid have real geometric overlap or embedding.
- Use `cut_rsolid(...)` for subtractive features and `intersect_rsolid(...)` for common-volume workflows.
- Validate body count and volume after major boolean operations.
