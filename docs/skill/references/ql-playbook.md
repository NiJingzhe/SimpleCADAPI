# QL Selection Playbook

Copy-paste patterns for selecting **what an operation produced** with QL —
side faces and rims of extrude-like features, output slots of primitives,
intersection curves (seams) of booleans, bore rims and root blends — and the
operations that consume those selections (fillet, chamfer, sketch datums,
extrude profiles).

Every pattern in the Ground rules and Patterns A/B was executed and checked
against `dev` @ `e87df6b` (2026-09-02, 33/33 checks across four harnesses:
extrude family, primitives, sweep/loft, D-boss seam). Snippets are trimmed
copies of the passing harness code. The recipes (selection loop, predicate
vocabulary, root blend, bore→rim chamfer, face→datum plane, facts printing)
were executed against `dev` @ `0ec8b76` (2026-09-06, 11/11 checks — see
Verification harnesses). Anything listed under "Verified boundaries" is a
real, current engine limitation — do not work around it silently; route
around it as shown.

## Ground rules

1. **Model inside `scad.GraphSession`.** Topology tracking, role tags, and
   name projection only exist on session paths. Legacy (session-less) calls
   attach whole-solid tags at most: no per-face roles, no projection, no
   `origin_role`/`output_role` evidence.

2. **Tag subshapes through the scope that will consume them.** Bindings live
   in a shape's own entity cache:

   ```python
   profile = scad.apply_tag_rselection(profile, [edge], "profile.long.a")
   ```

   Tagging an edge resolved from the *wire* under a face is invisible to the
   face (different cache). `apply_tag_rselection` returns a clone — always
   reassign the returned view. Pass `targets` as a **resolved list**; an
   unresolved selector as `targets` yields a clone foreign to the active
   session (the next operation rejects it with "graph node not owned by
   active graph"). Tag a shape **before** the next operation consumes it:
   retagging a consumed shape fails the same way — re-derive the selectors
   from the newest result instead.

3. **Enumerate with QL, not plural getters.** `ql.edges().resolve(shape)`,
   never bare `get_edges()` (raises by design; enumeration is QL-exclusive).

4. **Pick the naming channel by the reach you need:**

   | Channel | Example | Survives boolean | Survives fillet/chamfer |
   | --- | --- | --- | --- |
   | op-kwarg role naming | `extrude_rsolid(..., end_face_tag="cap.top")`, `make_box_rsolid(..., top_face_tag="base.top")` | yes (verified) | **no** (face channel gap) |
   | source-edge naming | `apply_tag_rselection(profile, [edge], "profile.long.a")` → side face; `apply_tag_rselection(result, [seam], "seam.d")` → fillet patch | yes (via kernel images) | **yes** (edge→patch projection) |
   | `origin_role("body"/"tool")` | parent argument of a boolean | single-step only | no |
   | `output_role("<slot>")` | `extrusion.end`, `box.top`, `fillet.patch` | single-step only | own op only |
   | plain user tag on a face | `apply_tag_rselection(solid, [face], "base.body")` | **no** (face-source gate) | **no** |

   "Single-step" means the metadata describes the last operation that touched
   the shape; the next tracked operation overwrites it. Long-range identity =
   op-kwarg names (across booleans) and edge-source names (across modifiers).

## The selection loop (card before cardinality)

Never hand a selector to an operation unresolved. Resolve it first,
print the card, read it, then assert:

```python
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
| Naming | `ql.tag("role.fastener_bore")`, wildcards `ql.tag("fillet.*")` | tags attached via `apply_tag_rselection(scope, targets=<resolved list>, tag=...)` |
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

## Pattern A — extrude-like outputs

The five canonical moves, on `extrude_rsolid` (identical selectors work for
`sweep_rsolid` / `loft_rsolid` and for primitives, which are the kernel-native
extrudes):

```python
with scad.GraphSession():
    wire = scad.make_rectangle_rwire(30.0, 10.0, (0, 0, 0), (0, 0, 1))
    profile = scad.make_face_from_wire_rface(wire)

    # 1) name profile edges through the profile scope (classifying by length
    #    and center sign stays the most robust addressing)
    for ent in ql.edges().resolve(profile):
        if abs(ent.get_length() - 30.0) < 1e-6 and ent.get_center().x > 0:
            profile = scad.apply_tag_rselection(profile, [ent], "profile.long.a")
        elif abs(ent.get_length() - 10.0) < 1e-6 and ent.get_center().y > 0:
            profile = scad.apply_tag_rselection(profile, [ent], "profile.short.a")

    solid = scad.extrude_rsolid(
        profile, (0, 0, 1), 8.0,
        start_face_tag="cap.bottom", end_face_tag="cap.top",
        side_faces_tag="wall.side",
    )

    # 1. side face by inherited profile-edge name (also: wall.side group = 4)
    ql.faces().where(ql.tag("profile.long.a")).resolve(solid)

    # 2. vertical corner edge shared by two side faces
    side_long = ql.faces().where(ql.tag("profile.long.a")).exactly(1)
    side_short = ql.faces().where(ql.tag("profile.short.a")).exactly(1)
    side_long.shared_boundary(side_short, "edge").resolve(solid)

    # 3. edge shared by the end face and one side face
    cap = ql.faces().where(ql.tag("cap.top")).exactly(1)
    cap.shared_boundary(side_long, "edge").resolve(solid)

    # 4. end face (kernel-role channel; kwarg name gives the same face)
    ql.faces().where(ql.output_role("extrusion.end")).resolve(solid)

    # 5. the end-face rim
    cap.boundary("edge").resolve(solid)
```

Verified extensions:

- **Primitives** carry the same slots natively: `box.top/bottom/front/back/
  left/right`, `cylinder.start/end/side/start_boundary/end_boundary/seam`,
  `cone.start/end/side/start_boundary/end_boundary/seam`. Query with
  `output_role(...)` or the matching `*_face_tag` / `*_edge_tag` kwarg.
  Box orientation for `width=x, height=y, depth=z`: front/back = ±x,
  left/right = ±y, top/bottom = ±z.
- **Planar profiles share the box axis convention**: for a +z normal,
  `width` spans global x (`make_rectangle_rwire(30, 10)` spans 30 in x and
  10 in y; identical on session and legacy paths). The in-plane basis is the
  reference vector projected onto the plane, so a +z-normal profile frame is
  exactly the global (x, y, z).
- **Seam edges without any name** — select by topology signature (the seam is
  the only full-height edge with a single incident face):

  ```python
  ql.edges().incident_face_count(exactly=1).resolve(solid)
  ```

- **sweep**: profile-edge names reach the swept side face exactly as with
  extrude (verified: circle edge name → cylindrical wall). `sweep.start/end`
  name the caps; cap rim and cap∩side shared edge select identically.
- **loft**: `loft.start/end` caps and the `side_faces_tag` group work; per-side
  identity is NOT stable (section correspondence is kernel-matched), so select
  sides as a group or post-hoc — never index them.

## Pattern B — boolean seam curves (D-boss recipe)

A D-shaped boss standing on the long side face of a bar base, unioned with a
1 mm dip into the base and a top that rises 4 mm above the bar: the seam is a
closed 3-D curve set running across the base side face, the base top face and
the bottom imprint. All of it is selectable, then filletable, in two moves.

```python
with scad.GraphSession():
    base = scad.make_box_rsolid(120.0, 30.0, 20.0, (0, 0, 0),
                                top_face_tag="base.top")

    # D boss = box U cylinder; cylinder bottom-face center sits at the
    # midpoint of the boss box's +y bottom edge -> classic D outline
    boss_box = scad.make_box_rsolid(24.0, 10.0, 24.0, (0, 19.0, 0.0))
    boss_cyl = scad.make_cylinder_rsolid(12.0, 24.0, (0, 24.0, 0.0), (0, 0, 1))
    boss = scad.union_rsolid(boss_box, boss_cyl)

    result = scad.union_rsolid(base, boss, clean=False)

    # parents by kernel-proven boolean origin role (arg 0 = body, arg 1 = tool)
    body_sel = ql.faces().where(ql.origin_role("body"))
    tool_sel = ql.faces().where(ql.origin_role("tool"))

    # the seam: edges with one distinct incident face per parent
    seam = ql.edges().incident_to(body_sel, tool_sel, distinct=True).resolve(result)

    # name the seam, then fillet it — the selector feeds fillet directly
    result = scad.apply_tag_rselection(result, seam, "seam.d")
    seam_sel = ql.edges().incident_to(body_sel, tool_sel, distinct=True)
    filleted = scad.fillet_rsolid(result, seam_sel, 2.0)

    # the patches inherit the seam-edge name (verified 7/7 patches)
    ql.faces().where(ql.tag("seam.d")).resolve(filleted)
```

Verified seam inventory for the dimensions above (`clean=False`): 13 edges —
2 vertical lines on the side face (±12, y=15), 5 edges on the base top plane
(the D outline where the boss crosses z=20: 1.0 + 5.367 + 14.056 + 5.367 +
1.0), 6 on the bottom plane (same outline at z=0 plus the 24-long dip
imprint). With `clean=True` the coplanar bottom pieces unify and part of the
imprint seam disappears — keep `clean=False` when the seam itself is the
selection target.

Facts that matter when filleting a seam:

- **`fillet_rsolid` accepts a `ShapeSelector`** for its `edges` argument; no
  need to materialize the list twice.
- A boss/base seam is mostly **concave**: the fillet ADDS volume
  (82780.7 → 82841.1 at r=2). Never assert `v1 < v0` on seam fillets.
- The whole seam filleted at once is a hard kernel case; if a radius fails,
  step down (2.0 → 1.5 → 1.0 verified ladder pattern).

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

Tag the bore wall right after the cut (Ground rule 2: tag before the next
operation consumes the shape), then chamfer its top rim:

```python
bore_faces = bore.resolve(solid)              # resolve first — see Ground rule 2
tagged = scad.apply_tag_rselection(scope=solid, targets=bore_faces,
                                   tag="role.fastener_bore")
bore_sel = ql.faces().where(ql.tag("role.fastener_bore")).exactly(1)
top_rim = ql.edges().incident_to(bore_sel, distinct=True).where(
    ql.prop("geom.center.z", ">=", 14.0))
rim_card = top_rim.resolve(tagged)
chamfed = scad.chamfer_rsolid(tagged, top_rim.exactly(len(rim_card)),
                              distance=1.0)
```

Gotchas this recipe absorbs:

- `incident_to` on a cylindrical wall returns seam edges too (the
  vertical seam of the cylinder surface sits mid-wall); filter rims by
  an axial coordinate window. The rim card is one closed arc of length
  `2*pi*r`.
- Passing an unresolved selector as `targets` (instead of the resolved
  list) produces a clone foreign to the active session; the next
  operation rejects it with "graph node not owned by active graph".
  Tagging a shape that a later operation has already consumed fails
  the same way — tag immediately after the op that produced the faces.
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
as a profile — same object, no re-derivation needed. Extruding the
top face of a 30×20 plate (bore opening r=6 after chamfer) by 2 mm
gives exactly `(30*20 - pi*6**2) * 2` volume.

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
ql.select(ql.faces().resolve(shape)).where(ql.prop("geom.type", "==", "PLANE")) \
  .order_by(ql.value("geom.area"), desc=True).limit(3).all()
```

## Verified boundaries

Current engine gaps found by the harnesses — each has a workaround above:

1. **Plain user tags on faces do not project through any later op.** The
   face-source projection gate (`autotag._project_source_bindings` with
   `require_lineage_policy=True`) passes only operation-output and topology
   naming; plain user bindings project from **edge** sources only. Use
   op-kwarg names for cross-boolean face identity, edge names for
   cross-modifier identity.
2. **Modifier face-source projection lacks `project_source_tags`**
   (`tracking.py`, `tracked_fillet`/`tracked_chamfer` face query). Face names
   — even op-kwarg ones that survive booleans — are dropped when the face is
   trimmed by a fillet/chamfer. The edge→patch channel is complete (7/7).
3. **`origin_role` / `output_role` are single-step metadata.** After the seam
   fillet, every face reports the fillet's own roles; the boolean body/tool
   partition is gone. Query parent identity immediately after the boolean, or
   carry it as a name.
4. **Primitive auto role tags (`face.box.top`, ...) do not project through
   booleans** — only kwarg-named slots (`top_face_tag="base.top"`) do.
5. **The planar profile in-plane basis switches discontinuously near
   vertical.** The reference-axis branch (`|z_z| > 0.9`) in the plane-basis
   helper swaps its reference between global X and Z, so sweeping a plane
   normal across roughly 25° from vertical rotates the in-plane frame
   abruptly. When normals vary, address profile edges by length and center
   sign rather than by axis assumptions.
6. **N-ary cut unrolls hop-by-hop**; multi-hop modification chains can lose
   projected bindings (later hops overwrite earlier witnesses for the same
   output). For long-range names across a cut chain, prefer naming after the
   final cut, or union-side naming.

## Verification harnesses

| Harness | Checks | Result |
| --- | --- | --- |
| extrude family (5 capabilities + group naming + geometry identity) — 2026-09-02, dev @ `e87df6b` | 8 | PASS |
| plane-axes convention (frame properties, rectangle extents on both paths) — 2026-09-02, dev @ `e87df6b` | 5 | PASS |
| primitives (box slots, rim, shared edge, kwarg naming, cylinder seam/rim/topology signature) — 2026-09-02, dev @ `e87df6b` | 8 | PASS |
| sweep + loft (profile-edge inheritance, caps, rims, shared edges, seam-by-topology) — 2026-09-02, dev @ `e87df6b` | 9 | PASS |
| D-boss seam (origin-role partition, 13-edge seam inventory, dual-parent witnesses, fillet, 7/7 patch naming) — 2026-09-02, dev @ `e87df6b` | 8 | PASS |
| recipes (loop card, predicate windows, bore→rim chamfer with resolved targets, root blend + lineage routes on a chamfered plate, face→datum plane mapping + face-profile extrude, facts printing) — 2026-09-06, dev @ `0ec8b76` | 11 | PASS |
