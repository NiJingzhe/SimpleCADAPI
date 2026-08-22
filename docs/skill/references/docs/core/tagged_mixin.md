# TaggedMixin

## Overview

`TaggedMixin` is the internal semantic binding and metadata mixin used by topology wrappers. Canonical tag ownership is source-preserving `TagBinding` data. `_tags` is only an effective-scope compatibility cache; user code must not treat it as writable truth.

User code should not call member tag mutators. The public tag API is functional:

- `apply_tag(shape, tag)` attaches one normalized tag.
- `apply_tag_rselection(scope, targets, tag, ...)` returns an independent semantic view and exposes explicit propagation policies.
- `list_tags(shape, scope=...)` returns tags in deterministic sorted order.
- `explain_tag(shape, tag, scope=...)` preserves binding and producer evidence.
- `select_faces_by_tag(...)`, `select_edges_by_tag(...)`, and QL predicates such as `ql.tag("role.*")` provide selection/query helpers.

## Tagging Mental Model

- Tags are normalized lowercase dot-separated semantic tokens.
- Examples: `role.mounting_surface`, `anchor.datum.primary`, `group.fasteners`, `face.top`, `edge.boundary`, `wire.outer`, `solid.boolean.cut`.
- New user assignments default to local topology propagation regardless of prefix.
- Downward inheritance is explicit and computed dynamically; bindings are not copied into every child.
- `effective` means local plus inherited and does not include lineage.
- `lineage` requires complete topology history and only follows derivations allowed by the binding policy.
- Numeric dimensions, measurements, and rich descriptive payloads belong in metadata, not tags.
- Geometry builders store structured geometry facts under `metadata["geo"]`.

## Public Tag Usage

```python
import simplecadapi as scad

box = scad.make_box_rsolid(width=5, height=3, depth=2)
scad.apply_tag(box, "role.bracket")
box.auto_tag_faces("box")

print(scad.list_tags(box))
top_faces = [face for face in box.get_faces() if "face.top" in scad.list_tags(face)]
print(len(top_faces))
```

## Explicit Propagation Example

```python
import simplecadapi as scad

body = scad.make_box_rsolid(width=10, height=10, depth=2)
tagged = scad.apply_tag_rselection(
    scope=body,
    targets=[body],
    tag="role.mounting_plate",
    topology_propagation=scad.TopologyPropagation.DOWNWARD,
)

face_hits = scad.select_faces_by_tag(
    solid=tagged,
    tag="role.mounting_plate",
    scope=scad.TagScope.INHERITED,
)
edge_hits = scad.select_edges_by_tag(
    shape=tagged,
    tag="role.mounting_plate",
    scope=scad.TagScope.INHERITED,
)

print(len(face_hits), len(edge_hits))
```

## Auto Tags

Primitives and modeling operations may attach normalized tags automatically:

- Primitive tags such as `geom.primitive.box`, `geom.primitive.cylinder`, and `geom.primitive.sphere`.
- Face tags from `auto_tag_faces(...)`, such as `face.top`, `face.bottom`, `face.side`, and `face.surface`.
- Wire tags such as `wire.outer` and `wire.inner`.
- Operation-level categorical tags such as `solid.boolean.cut` may remain local annotations.

Operation events and source roles are not tags. Proven `preserved`, `modified`,
or `generated` events and `body`/`tool` origins live in typed
`metadata["track"]`. Query them with `ql.operation_event(...)` and
`ql.origin_role(...)`. Missing correspondence remains `coverage="partial"` and
`status="unknown"`; it is never promoted to `generated` by default.

## Metadata Methods

`set_metadata(key, value)` and `get_metadata(key, default=None)` remain shape member methods for structured data.

```python
import simplecadapi as scad

part = scad.make_box_rsolid(10, 8, 5)
scad.apply_tag(part, "role.housing")
part.set_metadata("material", "6061-T6")
part.set_metadata("part_number", "mp-001-a")

print(part.get_metadata("material"))
print(part.get_metadata("geo"))
```

## QL Queries

```python
import simplecadapi as scad
from simplecadapi import ql as Q

body = scad.make_box_rsolid(10, 10, 2)
scad.apply_tag(body, "role.mounting_plate")
body.auto_tag_faces("box")

top_faces = Q.select(body.get_faces()).where(Q.tag("face.top")).all()
role_faces = Q.select(body.get_faces()).where(Q.tag("role.*", scope="effective")).all()

print(len(top_faces), len(role_faces))
```
