# Discipline: Geometric Validation

Deterministic checks decide pass/fail; scale them to the specification. Every
user-specified dimension requires a targeted measurement.

## Evidence labels

- **SDK contract:** `Solid.get_volume()` returns a volume measurement;
  `simplecadapi.inspect.brep` exposes diagnostic reports such as `valid`,
  volume, and shell closure for BREP outside a `GraphSession`.
- **Validation guidance:** the combination of checks below is a recommended
  gate, not a single SDK `Solid.is_valid()` method.

## Validity is not positive volume

Validity and positive volume answer different questions. Volume is meaningful
per solid, not only after aggregating multiple bodies; a positive and a negative
body can cancel in an aggregate and hide the problem.

After boolean/detail operations, check the gates relevant to the artifact:
`Solid.get_volume() > 0` for positive material volume, plus BREP diagnostics
from `simplecadapi.inspect.brep` (`inspect_shape_rbrepinspection` or
`inspect_step_rbrepinspection`) when validity and shell closure matter. These
inspection functions run outside `GraphSession`; they are diagnostic APIs, not
graph operations. `Solid` has no public `is_valid()` method.

A boolean can also leave a body that is geometrically right but topologically
invalid — correct bounds and volume, one bad face — which survives until the
next operation fails far from the cause. Gate every boolean result, not just
the final one.

## Incremental grounding

Every major step prints a small QL-derived fact: selected face count, a
center, an edge count, volume, bounding box. Print only the facts that
validate the current step — never whole solids or full model objects. This is
what makes drift catchable at the step that caused it instead of at final
review.

## Selection discipline

- Select by tags, axes, normals, positions, or QL predicates — not arbitrary
  topology indexes, which booleans and fillets renumber.
- Indexed getters (`get_faces(index)`, `get_edges(index)`, ...) are for
  intentional picks; they are preserved as graph geo-select nodes.
- `apply_tag(shape=..., tag=...)` attaches a tag to exactly the given shape
  with LOCAL scope — it never propagates downward; `list_tags(shape=...)`
  reads effective tags. Downward/topology-scoped propagation is only exposed
  by `apply_tag_rselection` with an explicit propagation policy. Keep numeric
  facts in metadata, never in tags.
- A QL-selected face or edge reused by a later feature is preserved as a
  stable geo-select node in replayable graphs.

## Replay as a gate

When a flow claims replayability, prove it: `export_model_json(session=...)`
→ `replay_model_json(json_str=...)` in a fresh process, and check the
replayed output count/values. A replay that was never run is a claim, not a
check.

## Spec-driven measurement

Every dimension, clearance, offset, and relationship in the brief gets a
targeted check:

- Distances and thicknesses: bounded measurements on selected geometry.
- Flush/centered interfaces: measured deltas, not visual impression.
- Patterns: at least two units measured for spacing/angle before trusting the
  pattern.
- Assemblies: solve residuals, coaxiality of mated axes, flush faces, repeated
  occurrences at named positions (`assembly-positioning.md`).

## Visual review converts to deterministic checks

A visual concern found at review (misplaced feature, wrong silhouette) is not
closed by "looks better now": convert it into a deterministic geometry check
that would have caught it, then run that check. Rendering and comparison
renders (`render_step_comparison_rpath`) are evidence for review — visual
similarity never replaces strict comparison where the contract requires it.

## Report only what ran

State the checks that actually executed, with their outcomes. An intended
check that was not run is reported as not run — implying success without
running a check is the cardinal reporting failure. Structural safety, fatigue,
thermal, vibration, tolerance compliance, and regulatory fitness are never
claimed from geometry alone (`manufacturing-boundaries.md`).
