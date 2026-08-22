# Workflow: Single-Part Modeling

Model one physical part from a refined brief to validated, optionally packaged
geometry.

## Goal and scope

Use for: new single-part models, dimension edits, feature additions, and part
repairs. Not for assemblies (use `assembly-product-build.md`), constrained
profiles as the core intent (use `sketch-feature-modeling.md`), or standard
components (check `standard-part-assembly.md` first).

## Task decomposition

```yaml
goal: validated single-solid part, optionally captured as .scadpkg
primary_domain: part-modeling
required_domains:
  - requirement-refinement
  - part-modeling
optional_domains:
  - sketch-and-features   # when the profile is constraint-driven
  - standard-parts        # when the part embeds a standard component
  - export-and-translation  # only when external formats are requested
artifacts:
  - brief
  - part source file (one part per file)
  - Solid or Part
  - GraphSession model JSON when replay is needed
validation_gates:
  - positive-volume closed solid after every boolean/detail step
  - every user-specified dimension measured
  - bounding box matches the brief
repair_routes:
  - boolean/fillet failure -> part-modeling (operation order, tool geometry)
  - profile evidence weak -> sketch-and-features (constraints) or part-modeling (direct wires)
```

## Steps

1. **Refine the requirement** (`domains/requirement-refinement.md`): units,
   dimensions, features, coordinate convention, each blocking unknown
   resolved ask-or-record, and validation targets that name the checks
   that will run. Record assumptions.
2. **Choose the construction strategy**
   (`discipline/mechanical-modeling.md`): profile-driven (sketch + extrude /
   revolve / sweep / loft) vs block-and-feature (base solid + subtractive
   features). Pick the one that makes the spec's controlling dimensions direct
   named parameters. Decide single solid vs part-of-assembly now.
3. **Fix the datum** (`discipline/datums-and-coordinate-systems.md`): origin,
   base plane, up axis from the functional interface.
4. **Model incrementally**
   (`discipline/feature-ordering.md`): base solid → major additions →
   subtractive features → shell → through-wall holes → fillets/chamfers last.
   One intentional operation per step, named parameters everywhere, keyword
   arguments in every call.
5. **Ground every step** (`discipline/geometric-validation.md`): after each
   major step print small QL-derived facts — selected face count, centers,
   edge counts, volume, bounds. Tag role surfaces
   (`role.mounting_surface`, `anchor.datum.primary`); keep numbers in
   metadata.
   Select detail edges per the edge-selection defaults in
   `discipline/geometric-validation.md` (shared_boundary first);
   run the selection evidence gate before every fillet/chamfer.
6. **Optional product boundary**: if the part is a durable deliverable, wrap
   with `@scad.part` and `capture(result, "out/<part>.scadpkg")`.
   (`domains/assembly-and-product.md`.)
7. **Export if requested** (`domains/export-and-translation.md`), only after
   validation passes.

## API pages to read

`make_box_rsolid`, `make_cylinder_rsolid`, `extrude_rsolid`,
`revolve_rsolid`, `sweep_rsolid`, `loft_rsolid`, `cut_rsolid`,
`union_rsolid`, `fillet_rsolid`, `chamfer_rsolid`, `shell_rsolid`,
`translate_shape`, `rotate_shape`, `mirror_shape`,
`linear_pattern_rsolidlist`, `radial_pattern_rsolidlist`, `apply_tag`,
`list_tags`, `part`, `capture` — plus any other API the design names, each
from `references/docs/api/<name>.md`.

## Validation gates

- One positive-volume, closed, valid solid after the final operation
  (per-solid checks, never aggregate-only).
- Visual acceptance minimum — each item produced before declaring done:
  1. whole-part views from at least two named directions (state the
     view; `auto` alone is not a direction);
  2. a close-up of every region a review comment touched, framed by a
     bbox-derived zoom estimate — re-rendering with hand-tweaked zoom
     until it looks right is enumeration, not framing;
  3. side-by-side with the reference image when one exists, and request
     an orthographic view or a key dimension when a single perspective
     reference is all there is;
  4. the selection-highlight render from the selection evidence gate.
- Every dimension in the brief verified by a targeted measurement.

- Boolean fails or yields multiple bodies → `part-modeling` boolean
  discipline: overlap, overshoot tools, isolate the failing pair.
- Fillet/chamfer fails → smaller radius, narrower edge selection, later in
  order.
- Dimension mismatch → re-measure against the brief; fix the named parameter,
  not the symptom.
- Repeated dead ends → `discipline/failure-and-repair.md`.

## Deliverables

Source file path, package path (if captured), QL validation facts actually
printed, assumptions made, and checks not run.
