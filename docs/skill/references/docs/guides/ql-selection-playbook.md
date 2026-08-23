# QL Selection Playbook

Copy-paste patterns for selecting faces and edges with QL, and the
operations that consume them (fillet, chamfer, sketch datums, extrude
profiles). Every snippet here runs as shown; properties and error
signatures were verified against the SDK.

## The selection loop (card before cardinality)

Never hand a selector to an operation unresolved. Resolve it first,
print the card, read it, then assert:

```python
from simplecadapi import ql

sel = ql.edges().shared_boundary(walls, top, to_kind="edge")
card = sel.resolve(solid)                     # probe without cardinality
for e in card:
    c = e.get_center()
    print(f"len={e.get_length():.3f} center=({c.x:.1f},{c.y:.1f},{c.z:.1f})")
sel = sel.exactly(len(card))                  # now freeze the count
```

Read the card against the geometry you imagined: expected count,
expected lengths (a full circle at radius r prints `2*pi*r`; a half
circle prints half that). A mismatch is a finding about the part, not
about QL. `.exactly(n)` failing loudly (`expected exactly 2 edge(s),
got 0`) is the gate working — widen or fix the window, never lower n
until the call succeeds.

## Predicate vocabulary

| Family | Examples | Notes |
| --- | --- | --- |
| Geometry | `ql.prop("geom.type", "==", "CYLINDER")`, `geom.center.x/y/z`, `geom.normal.x/y/z`, `geom.area`, `geom.length` | types are uppercase enums (`PLANE`, `CYLINDER`, ...) |
| Naming | `ql.tag("role.fastener_bore")`, wildcards `ql.tag("fillet.*")` | tags attached via `apply_tag_rselection(scope, targets=<selector>, tag=...)` |
| Lineage | `ql.output_role("fillet.patch")`, `ql.op("fillet")`, `ql.origin_role("contour_edge")` | see "Lineage routes" below |
| Boolean | `ql.and_(...)`, `ql.or_(...)`, `ql.not_(...)` | combine into one `.where(...)` |

**Coordinates take ranges, never equality.** Measured centers carry
float noise (`center.z` reads `15.000000000000002`); an `==` window
silently misses. Use paired bounds:
`ql.prop("geom.center.z", ">=", 14.5)` together with
`ql.prop("geom.center.z", "<=", 15.5)`.

**One property is never enough after a boolean or blend.** After a
fillet, the patch faces are cylinders too — `geom.type == "CYLINDER"`
matched five faces on a plate with one bore and four corner blends.
Discriminate by axis window plus size:

```python
bore = ql.faces().where(ql.and_(
    ql.prop("geom.type", "==", "CYLINDER"),
    ql.prop("geom.center.x", ">=", 14.9), ql.prop("geom.center.x", "<=", 15.1),
    ql.prop("geom.center.y", ">=", 9.9),  ql.prop("geom.center.y", "<=", 10.1),
    ql.prop("geom.area", ">=", 200.0),
)).exactly(1)
```

## Recipe: root blend via shared boundary

Edges shared between two named bodies are the first-choice selection
(`discipline/geometric-validation.md`, edge-selection defaults):

```python
walls     = ql.faces().where(ql.prop("geom.type", "==", "CYLINDER"))
plate_top = ql.faces().where(ql.and_(
    ql.prop("geom.normal.z", ">=", 0.999),
    ql.prop("geom.center.z", ">=", 14.5), ql.prop("geom.center.z", "<=", 15.5)))
root = walls.shared_boundary(plate_top, to_kind="edge")

with GraphSession(graph_id="blend") as s:
    blended = scad.fillet_rsolid(solid, root.exactly(card_count), radius=2.0,
                                 generated_faces_tag="fillet.root_patch")
    s.capture_result(value=blended)
```

### Shared-boundary failure signatures (read them, do not fight them)

A shared boundary resolves against the real topology; when it does not
match the shape you imagined, the difference is diagnostic:

| Card looks like | Cause | Fillet result |
| --- | --- | --- |
| One closed arc, length `2*pi*r` | feature seated with clearance (axis-to-wall distance > radius) | succeeds |
| Two arcs meeting at one point, lengths summing to `2*pi*r` | **tangency**: axis-to-wall distance exactly equals the radius; outline touches the wall in one point | kernel crash `TopOpeBRepDS_DataStructure::Point` at any radius |
| Half arc / extra short arcs | feature overhangs the wall (axis outside or on the wall) | kernel build aborts |

Reason from these the same way for every shared-boundary case: compare
the card's segment count and lengths with the intersection curve you
imagined; look for the singular point where segments meet; treat
"selection resolved fine but every radius crashes" as evidence of a
degenerate configuration in the design, not a selector bug. Before
blending a seated feature, assert clearance: axis-to-neighboring-wall
distance must exceed the blend radius (same family as fastener
envelopes, `discipline/mechanical-modeling.md`).

## Recipe: tagged bore -> rim chamfer

```python
holed = scad.apply_tag_rselection(scope=holed, targets=bore_wall_selector,
                                  tag="role.fastener_bore")
bore    = ql.faces().where(ql.tag("role.fastener_bore")).exactly(1)
top_rim = ql.edges().incident_to(bore, distinct=True).where(
    ql.prop("geom.center.z", ">=", 14.0))
chamfed = scad.chamfer_rsolid(holed, top_rim.exactly(top_rim.resolve(holed).__len__()),
                              distance=1.0)
```

Gotchas this recipe absorbs:

- `incident_to` on a cylindrical wall returns seam edges too (the
  vertical seam of the cylinder surface sits mid-wall); filter rims by
  an axial coordinate window.
- Tagging a bare sub-shape taken from `get_faces()` fails graph
  ownership ("assignment scope is not produced by the active
  GraphSession"). Tag through the scope with `apply_tag_rselection`.
- Objects live in one `GraphSession`; passing a solid into operations
  under another session fails loudly. Keep the whole build in one.

## Recipe: selected face -> sketch datum plane

`make_sketch_rsketch(plane=...)` accepts `"XY"/"XZ"/"YZ"` or a plane
mapping — never a Face. Derive the mapping from the selected face:

```python
def plane_mapping_from_face(face):
    c, n = face.get_center(), face.get_normal_at()
    z = (n.x, n.y, n.z)
    ref = (1.0, 0.0, 0.0) if abs(z[2]) >= 0.9 else (0.0, 0.0, 1.0)
    dot = sum(ref[i] * z[i] for i in range(3))
    x = [ref[i] - dot * z[i] for i in range(3)]
    m = sum(v * v for v in x) ** 0.5
    x = [v / m for v in x]
    y = (z[1]*x[2]-z[2]*x[1], z[2]*x[0]-z[0]*x[2], z[0]*x[1]-z[1]*x[0])
    return {"origin": (c.x, c.y, c.z), "x_axis": tuple(x), "y_axis": y}

sketch = scad.make_sketch_rsketch(name="on_face",
                                  plane=plane_mapping_from_face(selected_face))
```

Pick the datum face itself with QL when the intent is structural
("largest up-facing face") rather than positional:

```python
datum = (ql.faces().where(ql.prop("geom.normal.z", ">=", 0.999))
         .order_by(ql.value("geom.area"), desc=True).take(1).exactly(1))
```

`extrude_rsolid(profile=..., ...)` accepts the selected Face directly
as a profile — same object, no re-derivation needed.

## Lineage routes (proving what an operation produced)

| Question | Route | Verified semantics |
| --- | --- | --- |
| Which faces did this operation generate? | `generated_faces_tag="name"` param, then `ql.tag("name")` | kernel-proven patch faces only |
| Same, without pre-declaring a tag | `ql.output_role("fillet.patch")` | faces whose track metadata carries `result_roles` and `events=["generated"]` |
| Everything the operation touched (new + modified)? | `ql.op("fillet")` | superset: includes faces with `events=["modified"]` |

Counting patch faces after a blend is the proof that the blend landed
where intended — pair it with the highlight render from the selection
evidence gate. Track metadata is authoritative: a generated face
carries `events: ["generated"]`, a reshaped survivor carries
`["modified"]`.

## Facts printing

For ad-hoc facts outside selectors, the list query mirrors the selector
API:

```python
ql.select(faces).where(ql.prop("geom.type", "==", "PLANE")) \
  .order_by(ql.value("geom.area"), desc=True).limit(3).all()
```
