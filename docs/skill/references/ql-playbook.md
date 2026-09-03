# QL Selection Playbook

Verified query patterns for selecting **what an operation produced**: side
faces and rims of extrude-like features, output slots of primitives, and the
intersection curves (seams) of booleans — then feeding those selections into
modifiers such as fillet.

Every pattern in this file was executed and checked against `dev` @ `88f251c`
(2026-09-02, 33/33 checks across four harnesses: extrude family, primitives,
sweep/loft, D-boss seam). Snippets are trimmed copies of the passing harness
code. Anything listed under "Verified boundaries" is a real, current engine
limitation — do not work around it silently; route around it as shown.

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
   reassign the returned view.

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
5. **Planar profile axes now match the box convention** (fixed by
   `fix/plane-axes-convention`): `_orthonormal_plane_axes` builds the in-plane
   basis by projecting the reference vector (Gram-Schmidt), so for a +z normal
   width spans global x, exactly like `make_box_rsolid`. Before the fix,
   `make_rectangle_rwire(30, 10)` silently spanned 10 in x and 30 in y; the
   harnesses classified profile edges by length and center sign, which stays
   the most robust addressing. Known residual behavior (separate issue): the
   reference-axis branch (`|z_z| > 0.9`) still switches the in-plane basis
   discontinuously near ~25° from vertical.
6. **N-ary cut unrolls hop-by-hop**; multi-hop modification chains can lose
   projected bindings (later hops overwrite earlier witnesses for the same
   output). For long-range names across a cut chain, prefer naming after the
   final cut, or union-side naming.

## Verification harnesses (2026-09-02, dev @ 88f251c)

| Harness | Checks | Result |
| --- | --- | --- |
| extrude family (5 capabilities + group naming + geometry identity) | 8 | PASS |
| primitives (box slots, rim, shared edge, kwarg naming, cylinder seam/rim/topology signature) | 8 | PASS |
| sweep + loft (profile-edge inheritance, caps, rims, shared edges, seam-by-topology) | 9 | PASS |
| D-boss seam (origin-role partition, 13-edge seam inventory, dual-parent witnesses, fillet, 7/7 patch naming) | 8 | PASS |
