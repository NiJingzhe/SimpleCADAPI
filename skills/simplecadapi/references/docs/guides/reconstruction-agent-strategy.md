# Reconstruction Agent Strategy

This guide is advisory. The normative run, evidence, classification, and
artifact rules are in
[`reconstruction-agent-test-prompt.md`](reconstruction-agent-test-prompt.md).

## Investigate Economically

Start with the cheapest evidence that can falsify the current hypothesis:

```text
inspect_step_rsummary
inspect_step_entity_rdescriptor
inspect_topology_neighborhood_rdescriptor
inspect_section_rdescriptor
inspect_face_boundaries_rdescriptor
compare_global_properties_rdescriptor
```

Use compact boundary and section reports first. Request complete curve/surface
definitions only for entities selected by a specific hypothesis. Persist large
arrays directly to authorized parameter files instead of echoing them through
conversation context.

Call `inspect_step_rsummary(..., include_parameter_groups=True)` once when
analytic radii or repeated carrier signatures may be informative. For exact
local evidence, use targeted curve/surface definition flags with explicit
control-point limits. An untrimmed carrier definition is incomplete without its
UV range, ordered trim-loop, and seam evidence.

Useful focused interfaces include `inspect_topology_rdescriptor`,
`measure_entity_relation_rdescriptor`, `inspect_point_rdescriptor`,
`inspect_nearby_entities_rdescriptor`, `compare_entities_rdescriptor`,
`render_region_rpath`, and `compare_sections_rdescriptor`. Use
`make_surface_patch_rface` and `loft_rshell` only for construction, outside
inspection graphs.

Treat repetition and symmetry as hypotheses. Verify positions, axes, spacing,
orientation, and adjacency on at least two units before patterning.

## Choose A Feature Family

Use observed carrier and section behavior:

```text
shared axis + rotational sections       -> revolve
stable translated profile               -> extrude
profile transported along a path        -> sweep
ordered changing section family         -> Loft
verified equal angular/linear units      -> one unit + pattern
several local signatures                 -> ordered mixed feature tree
none                                     -> fitted freeform or transcription
```

A loop on a final planar face may be a later hole, slot, notch, or pocket rather
than part of the base profile. Inspect adjacent side carriers and operation
direction before folding loops into one profile.

For each base region, opening, or local detail, record a compact provenance row:
observed boundary, adjacent carrier/continuation evidence, proposed operation,
direction or axis, confidence, and the section/entity check that could falsify
it before full construction.

## Profile Authoring

Prefer a declarative Sketch for a planar, editable design profile when the
available constraints represent the evidence. Record plane mapping, closure,
arc direction, spline definition, solve status, and remaining DOF.

Use `make_sketch_rsketch`, stable `add_*_rsketch` entities, and evidence-backed
constraints. Promote with `make_face_from_sketch_rface` or
`make_wire_from_sketch_rwire`. A Sketch wrapping a prebuilt Wire does not recover
Sketch intent. Use `inner_profiles` only when adjacent-carrier evidence shows the
loops belong to the same generating profile.

`add_arc_rsketch` follows the positive local angular sweep, so endpoint order is
meaningful. For exact splines, preserve degree, knots, multiplicities, weights,
and shared endpoint references. When only coordinates are known, label the
result coordinate-locked rather than claiming inferred parametric intent.

Direct Wire construction is appropriate for:

- non-planar paths and guides;
- exact freeform carrier/trim transcription;
- unsupported Sketch entities or relationships;
- report-derived geometry whose projection changes measured control data;
- a demonstrated Sketch-path regression.

Sketch is an authoring preference, not an acceptance gate. Candidate-to-target
evidence decides reconstruction quality.

When Sketch promotion may change measured geometry, build Wire and Sketch from
one parameter source, compare closure/area/bounds/segmentation first, then replay
complete candidates in fresh processes. Use cheap aggregate and bounded sampled
diagnostics to falsify hypotheses or localize differences, never as acceptance
gates. The trusted evaluator still runs strict material evidence for every solid
target. Prefer compact design intent over arbitrary point clouds, and never label
a polyline or fitted Loft as exact NURBS transcription.

## Boolean Discipline

Prefer a simple base followed by independent local additive/subtractive tools.
Overshoot through-cut tools intentionally rather than ending them coincidently.
Validate one representative feature before repeating it.

If a Boolean fails:

1. verify valid operands and positive-volume overlap;
2. remove accidental tangency/coincident terminal faces;
3. isolate and simplify the base/tool pair;
4. use `TrackingPolicy.GRAPH` only to reduce lineage cost, never to repair geometry;
5. use `cut_rsolid(..., skip_non_intersecting=False)` for strict diagnostics;
6. reconsider operation order after repeated failure.

Never call a skipped or ineffective Cut a completed feature.
Prefer isolated or flat-list local cuts over whole-model complements, large
clipping constructions, or Boolean workarounds that obscure the failing feature.

## Diagnostic Escalation

Use expensive operations only when justified:

- strict material comparison for every solid submitted to trusted evaluation;
- sampled boundary distance to localize approximation, not prove equality;
- material difference regions only from a strict component-bearing result;
- exact BREP comparison only after lower-tier geometry proof.

`compare_material_rdescriptor(include_components=False)` is an estimate only.
Strict proof and reusable difference regions require `include_components=True`.
Start `compare_boundary_distance_rdescriptor` at no more than 200 samples and
scope it with face IDs when possible. Use `inspect_difference_regions_rdescriptor`
only with compatible cached evidence, and reserve `compare_steps_rbrepcomparison`
for a configured `exact_brep` attempt.

Cache results by target hash, candidate hash, and arguments. Do not repeat an
unchanged expensive call.

## Iteration Selection

Record one compact row per iteration:

- falsifiable hypothesis and changed parameters/operation order;
- replay, validity, target-kind, and STEP roundtrip status;
- global and focused diagnostic deltas;
- strongest acceptance proof attempted;
- provenance changes;
- evidence for the next decision.

Preserve the best valid candidate. One parameter retry may retain a construction
strategy; repeated non-improvement should change the feature hypothesis rather
than continue blind tuning.

Global similarity cannot override a locally falsified feature family. Conversely,
stop tuning credible serialization-only floating-point drift once the configured
contract gates pass.
