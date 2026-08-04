# Reconstruction Agent Test Prompt

Use this specification to test a fresh Agent on STEP-to-SimpleCADAPI
reconstruction without exposing an existing solution.

## Start Message

Send the Agent only this wrapper with all placeholders replaced:

```text
Read and follow this test specification completely:
{SIMPLECADAPI_ROOT}/docs/guides/reconstruction-agent-test-prompt.md

Configuration:
SIMPLECADAPI_ROOT = {SIMPLECADAPI_ROOT}
TARGET_DIR = {TARGET_DIR}
CASE_NAME = {CASE_NAME}
OUTPUT_DIR = {OUTPUT_DIR}
MAX_ITERATIONS = {MAX_ITERATIONS}
BENCHMARK_MODE = {BENCHMARK_MODE}
MATERIAL_TIMEOUT_SECONDS = {MATERIAL_TIMEOUT_SECONDS}

The configuration above overrides examples in the specification. Start the
test immediately and continue through independent replay, evaluation, and final
classification. Do not modify the SDK or target baseline.
```

Use a new, empty `OUTPUT_DIR` for every Agent.

## Objective

Reconstruct `{CASE_NAME}.step` as a readable, independently replayable
SimpleCADAPI program.

The default objective is `geometry_equivalent`, not original feature history.
Geometry equivalence means that strict bidirectional material difference proves
the same occupied material point set. Matching renders, volume, area, bounds,
centroid, sections, or topology counts alone is not proof.

Acceptance follows the priority order in Classification:

1. BREP topology identity is the best endpoint — reaching it is complete
   reverse engineering.
2. Identical structure with minor parameter drift attributable to
   export/serialization float error is acceptable; do not keep optimizing
   float-level residuals.
3. A visually close but structurally different candidate is a valid stop only
   when you cannot find a better feature operation order/combination, or the
   required operation type is not supported by the SDK. Otherwise keep
   iterating.

`exact_brep` evaluation is expensive and must not consume iterations before the
candidate is near structure match.

## Input Isolation

The only permitted case-specific inputs are files directly under `TARGET_DIR`:

```text
{CASE_NAME}.step
{CASE_NAME}_brep_report.json
{CASE_NAME}_step_render.png
{CASE_NAME}_mesh_render.png
```

Rules:

1. Do not search outside `TARGET_DIR` for `{CASE_NAME}`, previous candidates,
   reconstruction scripts, parameter files, summaries, scene packages, or
   Agent outputs.
2. Do not inspect Git history, deleted files, caches, temporary directories, or
   another Agent's output to recover a prior solution.
3. You may read SDK source, public API documentation, tests, and generic
   reverse-engineering guidance, but not another reconstruction of this case.
4. Write every generated artifact under `OUTPUT_DIR`.

If a forbidden solution artifact is encountered accidentally, do not read it;
record the path and continue from allowed inputs only.

## Benchmark Modes

### inspection-only reconstruction

Use the target only through approved BREP inspection/query tools and supplied
renders. Do not read complete control-point, knot, multiplicity, or weight
arrays from the report. Do not request `include_curve_definition`,
`include_surface_definition`, or boundary `include_curve_definitions`; those
options expose the same exact arrays through tools.

### report-assisted reconstruction

You may read the complete BREP report, including exact curve and surface data.
Record which values were copied, inferred, or fitted.

### exact BREP transcription

Complete carrier, trim, and topology data may be used. Label the result as
transcription, not inferred feature reconstruction.

## Hard Constraints

1. Use public SimpleCADAPI modeling APIs for the final candidate.
2. Do not modify `SIMPLECADAPI_ROOT/src`, tests, tools, or target inputs.
3. The final program must not read or import the target STEP at runtime.
4. Do not copy, encode, embed, or re-export target STEP contents.
5. A separate reconstruction-parameter JSON is allowed, but it must contain
   explicit inferred/fitted parameters and work without the target.
6. Do not replace an open-shell target with a fabricated solid.
7. Do not use network services or external CAD applications.
8. Do not add Agent tools or SDK operations during the test. Work with the
   existing API and focused tool set.
9. Follow the Sketch-first profile policy in Phase 2. A planar profile that
   drives an extrude, revolve, or additive/subtractive cut must start as a
   declarative Sketch unless a documented exception applies. Wrapping an
   already-built Wire in `Sketch([wire])` does not satisfy this rule.

## Minimal Tool Policy

Start with the cheapest evidence that can test a concrete hypothesis:

```text
get_model_summary
inspect_entity
get_topology_neighborhood
make_section
extract_face_boundaries
compare_global_properties
```

Use `get_model_summary(include_parameter_groups=true)` once during initial
characterization when analytic radii or repeated carrier signatures may be
informative. Carrier, canonical-axis, and adjacency-signature groups are
bounded descriptive multiplicities only. They do not prove a pattern.

Use `extract_face_boundaries(compact=true)` before requesting sampled boundary
arrays. Compact mode preserves ordered edge occurrences, orientation, type,
length, endpoints, and key scalar parameters while keeping context small.

Use `make_section(compact=true)` for initial section-family and opening checks.
Request sampled section arrays only for a specific fit or distance question.

In report-assisted mode, after identifying the exact entities needed by a
hypothesis, prefer targeted definitions over reading the full report:

- use `inspect_entity(include_curve_definition=true)` for one curve. For a
  B-spline/Bezier edge this returns the complete definition without a
  control-point limit, so inspect its pole count first;
- use `extract_face_boundaries(compact=true,
  include_curve_definitions=true, curve_definition_edge_ids=[...])` for an
  explicitly selected set of boundary curves. Definitions are deduplicated and
  sorted by stable edge ID; read the loop `edges` arrays for coedge order.
  Unsupported carrier types return `available=false`, not a partial definition;
- use `inspect_entity(include_surface_definition=true,
  max_surface_control_points=...)` for one B-spline/Bezier carrier surface.

Start with the default surface and boundary-batch limits. Increase a limit only
after recording the entity's degree and control-point counts and why the
complete definition is needed. `max_total_control_points` counts selected
unique B-spline/Bezier poles; it does not bound analytic edge count or the whole
payload. Exact surface definitions describe untrimmed carriers; always retain
UV ranges and trim-loop evidence separately. Do not echo complete arrays into
the iteration log or subsequent prompts; persist them directly as explicit
reconstruction parameters under `OUTPUT_DIR` and keep only a concise provenance
summary in conversation context.

Use these only when a specific local question requires them:

```text
measure_relation
probe_point
find_nearby_entities
compare_entities
render_region
compare_sections
```

Expensive tools are not default iteration steps:

```text
compute_material_difference
compare_boundary_distance
build_difference_regions
compare_brep_strict
```

Cost rules:

- Run `compute_material_difference` only for the final candidate or when global
  evidence says the candidate is close enough to justify a Boolean. Agent-tool
  calls default to volume-only mode, which uses one intersection and reports
  `method=common_volume` without component lists. Because subtracting a common
  volume can lose a small residual at large model scales, use it only as an
  estimate. Request `include_components=true` for a strict material check; this
  uses two directional cuts and is also required for difference regions or STEP
  export. Leave `boolean_tolerance` unset for equality proof; a fuzzy result is
  diagnostic only and reports `strict_equality_supported=false`.
- Skip the Boolean when the absolute global volume delta already exceeds the
  strict material tolerance: equal point sets must have equal volume, so this
  cheaply disproves equivalence.
- Bound it by `MATERIAL_TIMEOUT_SECONDS`. A timeout means equivalence remains
  unproved; it does not mean the model is equal.
- Use `compare_boundary_distance` only to diagnose an approximation. Start with
  at most 200 samples and use `target_face_ids`/`current_face_ids` when a local
  region is known.
- `build_difference_regions` defaults to Boolean material components. Reuse an
  existing `material_result` only when it was created with
  `include_components=true`; include boundary clustering only when needed and
  reuse a boundary result created with `include_records=true`.
- Do not run `compare_brep_strict` unless Exact BREP was explicitly requested.
- Never repeat an expensive result when target hash, candidate hash, and tool
  options are unchanged.

## Phase 1: Investigate

1. Record target hashes and declare the benchmark mode.
2. Inspect validity, body/shell counts, bounds, volume, area, centroid, and
   surface/curve type statistics.
3. Establish coordinate semantics, openings, cavities, and likely feature
   families.
4. Treat symmetry and repetition as hypotheses, never defaults:
   - inspect scalar carrier groups and their counts;
   - look for a plausible common factor only as a candidate unit count;
   - verify spatial center/axis spacing, orientation, and local adjacency on at
     least two proposed units;
   - reduce the model to one repeated unit only after those independent checks
     agree;
   - if they do not agree, abandon repetition and evaluate revolve, extrude,
     sweep, Loft, mixed-feature, or freeform explanations instead.
5. Use a small number of informative sections or local queries.
6. Write one explicit construction hypothesis before modeling. State its
   parameters, discrete choices, and evidence that could falsify it.
7. For every proposed feature-driving profile, record its plane, intended
   feature, and authoring choice: declarative Sketch, path/guide Wire, or exact
   geometry transcription.

Do not inspect hundreds of entities without a hypothesis.

### Feature provenance and operation order

A loop visible on a final planar face is not automatically part of the profile
that generated the surrounding body. It may instead be the trace of a later
hole, slot, notch, pocket, trim, or intersecting feature.

Before placing an inner loop or local concavity into a generating profile:

1. Inspect its topology neighborhood and at least one adjacent side face.
2. Record the adjacent carrier type, axis or normal, and whether the same loop
   continues to another terminal face.
3. Infer the likely operation direction from those carriers. For example,
   translated side carriers support an extrusion or cut, while rotational
   carriers sharing an axis support a revolved feature.
4. Check whether other loops on the same final face have the same carrier and
   direction evidence. If they do not, use a mixed ordered feature tree rather
   than forcing all loops into one sketch operation.
5. Falsify the proposed operation with one section or representative entity
   comparison before constructing the full model.

Maintain a compact feature-provenance table in the iteration log with one row
per proposed base region, opening, or local detail: observed final boundary,
adjacent carrier evidence, inferred operation, direction/axis, and confidence.
The table describes reasoning; it must not be copied into the final program as
target-dependent runtime data.

### Conditional feature-family decision

Use this decision order rather than forcing every model into a repeated-unit
construction:

```text
dominant shared axis + rotationally invariant sections -> revolve/turning
dominant direction + stable translated profile         -> extrude
profile transported along a path                       -> sweep
ordered section family with changing shape             -> Loft
verified equal angular/linear units                     -> construct one unit + pattern
several local signatures                                -> mixed feature tree
none of the above                                       -> fitted freeform or transcription
```

Equal type counts, equal radii, or a count divisible by `N` are insufficient
on their own. A non-repetitive part must not be coerced into a pattern merely
because several faces share a carrier type.

## Phase 2: Construct

Create:

```text
{OUTPUT_DIR}/{CASE_NAME}_rebuild_simplecadapi.py
```

The program must:

- be readable and parameterized;
- run in a fresh process;
- export `{CASE_NAME}_rebuilt.step` under `OUTPUT_DIR`;
- produce a valid BREP;
- use `@scad.model` and strict replay when supported;
- clearly label exact transcription, fitting, and approximation.

Prefer compact design intent over arbitrary point clouds. Do not describe a
polyline or fitted Loft as exact NURBS transcription.

### Sketch-first profile policy

Use a declarative Sketch as the default authoring representation for a planar
closed profile that drives:

- an extrusion or revolution;
- an additive boss or subtractive hole, pocket, slot, notch, or through-cut;
- a planar section whose design intent is a named, editable profile.

Build it with `make_sketch_rsketch(...)`, stable point/entity IDs,
`add_*_rsketch(...)`, and constraints supported by the reconstruction
evidence. Promote it with `make_face_from_sketch_rface(...)` or, when a feature
requires a section Wire, `make_wire_from_sketch_rwire(...)`. Use
`require_fully_constrained=True` when the intended dimensions and relations can
be represented without inventing unsupported design intent.

Prefer dimensional and geometric constraints such as radius, distance,
horizontal/vertical, parallel, perpendicular, tangent, and concentric when
they are supported by evidence. If only recovered coordinates are known,
fixed points are allowed for deterministic replay, but label the result as a
coordinate-locked reconstruction rather than claiming recovered parametric
intent.

Use `inner_profiles=(...)` only when topology and adjacent-carrier evidence
show that the loops belong to the same generating Sketch. Model a later hole,
slot, or pocket as its own ordered feature instead of folding its final-face
trace into the base Sketch.

Before promoting a Sketch profile, verify:

- the Sketch plane and local-to-world mapping;
- a closed non-construction loop with the intended entity segmentation;
- Arc sweep direction and minor/major choice; `add_arc_rsketch(...)` uses the
  positive local angular sweep, so swapping endpoints changes the geometry;
- B-spline degree, knots, multiplicities, weights, and endpoint poles; use the
  shared endpoint point refs as first/last poles when exact connectivity is
  intended;
- solve status, remaining DOF, and diagnostics.

Direct Wire construction is allowed only for a concrete reason:

- a non-planar path, 3-D guide curve, Helix, or other path geometry;
- freeform carrier/trim geometry or exact BREP/NURBS transcription that is not
  a planar design Sketch;
- an entity, constraint, or multi-loop relationship the current Sketch API
  cannot represent faithfully;
- report-derived geometry whose projection onto a Sketch plane changes its
  control data or measured geometry;
- a demonstrated kernel or modeling regression in the Sketch path.

Do not force a spatial path, freeform surface boundary, or unsupported exact
transcription into a fake Sketch merely to satisfy Sketch-first. Record every
direct-Wire exception and its evidence in the iteration log.

When a planar Wire exception is proposed, or when Sketch promotion may change
geometry, use the cheapest A/B sequence that can decide it:

1. Keep one shared parameter source and independently build Wire and Sketch
   profiles.
2. Compare profile closure, area, bounds, edge count, and ordered edge lengths.
3. If those agree, rebuild the complete Wire and Sketch candidates in fresh
   processes and run `compare_global_properties`.
4. Only when the candidates are close enough, compare strict bidirectional
   material and a bounded boundary distance. Do not run `compare_brep_strict`
   solely for this A/B unless `exact_brep` was requested.
5. Prefer Sketch when it preserves or improves target evidence. Keep Wire when
   Sketch introduces avoidable measured drift or changes the acceptance result,
   and document the exception rather than hiding it.

Candidate-to-target evidence remains the acceptance basis. Wire-to-Sketch A/B
selects the authoring strategy; it does not by itself prove reconstruction
quality.

### Boolean construction policy

Use the simplest direct feature sequence supported by the evidence. Prefer a
base feature followed by independent local additive or subtractive tools over
whole-model complements, large clipping constructions, or coincident Boolean
operands.

For a through opening or slot, prefer a simple cutter that deliberately
overshoots both terminal sides. For multiple local cuts, validate one
representative base/tool pair before constructing all tools, then apply the
tools individually or as a flat list so the failing feature can be identified.

If a Boolean fails:

1. Verify that the base and tool are each valid solids and that the intended
   overlap has positive volume, not only overlapping bounding boxes.
2. Remove exact tangencies and coincident end faces with small intentional tool
   overshoot; do not change target dimensions merely to hide the failure.
3. Retry the isolated base/tool pair with a simpler tool and no unnecessary
   upstream union or complement.
4. Use `TrackingPolicy.GRAPH` when topology lineage is unnecessary and history
   tracking is the suspected cost. This does not repair wrong geometry or alter
   intersection validation.
5. Use `skip_non_intersecting=False` for strict cut diagnostics when available;
   it exposes a missed cut instead of silently accepting it.
6. After repeated failure, reconsider the operation order or feature-family
   hypothesis. Do not replace a locally supported feature tree with a global
   clipping construction solely as a Boolean workaround.

Never classify a skipped or silently ineffective cut as a completed feature.

## Phase 3: Iterate

For each complete candidate iteration:

1. Run the program in a fresh process and regenerate the STEP.
2. Require successful exit, a newly generated STEP, and valid BREP.
3. For every promoted Sketch used by the candidate, require a closed profile
   and record solve status, DOF, and diagnostics.
4. Run `compare_global_properties`.
5. If global/material scale is clearly wrong, fix the construction before any
   dense boundary or topology work.
6. Use sections or local diagnostics only to answer the next modeling question.
7. When the candidate is plausibly final, attempt one bounded
   `compute_material_difference(include_components=true)` for the strict
   material result.

An attempt that fails to replay, does not generate a new STEP, or produces an
invalid BREP is a failed construction attempt, not a complete candidate
iteration. Record the failure and diagnostic evidence, but do not consume
`MAX_ITERATIONS` or count it toward the three non-improving complete iterations.
Do not make more than three consecutive failed construction attempts on the
same feature family or Boolean arrangement; revert to the best valid candidate
and change the hypothesis or operation order.

One parameter-only retry may reuse the same construction strategy. A changed
feature family or construction method starts a new complete iteration only when
it produces a freshly replayed valid candidate.

Stop blind tuning after three non-improving iterations. Preserve the best valid
candidate and report the blocker. Select the best candidate using material,
focused section/boundary, carrier, and global evidence together; global
properties alone must not override a locally falsified feature family.

## Classification

Assign exactly one classification.

### exact_brep

Complete reverse engineering — the best endpoint. Requires fresh replay, valid
BREP, strict bidirectional material equality, geometry-labelled incidence graph
isomorphism, and required representation checks. Minor parameter drift
attributable to export float error does not break topology identity. This is
expensive: evaluate it only when the candidate is near structure match, not as
a routine iteration step.

### geometry_equivalent

Requires fresh replay, valid BREP, and strict bidirectional material equality.
Boundary, section, seam, surface representation, and topology equality are not
additional requirements. A structure-matched candidate with float-level
parameter drift classifies here or as `exact_brep` — never as `approximation`.

### approximation

Use when a valid replayable candidate exists but strict material equality
fails or remains unproved (including Boolean timeout), AND optimization is
genuinely exhausted: no better feature operation order/combination is findable,
or the required operation type is not supported by the SDK. Record which reason
and its evidence. Report measured global and local errors without upgrading the
result based on visual similarity. A "looks close" result is not a valid stop
on its own.

### unsupported_or_incomplete

Use when no valid replayable candidate exists or the target cannot be
represented by the available SDK. Do not manufacture a success-shaped result.

## Required Artifacts

Keep the artifact set minimal:

```text
{CASE_NAME}_rebuild_simplecadapi.py
{CASE_NAME}_reconstruction_params.json        # only if needed
{CASE_NAME}_rebuilt.step
{CASE_NAME}_rebuilt_brep_report.json
{CASE_NAME}_evaluation.json
{CASE_NAME}_iteration_log.json
```

The iteration log records:

- hypothesis and exact source/parameter change;
- replay and validity result;
- Sketch solve evidence and every direct-Wire exception;
- global errors;
- diagnostics actually used and why;
- strict material result or timeout when attempted;
- evidence selecting the next change.

Optional renders or Scene packages may be generated for human inspection, but
they are not acceptance evidence.

## Final Response

Report concisely:

- classification and iteration count;
- construction hypothesis and final command sequence;
- Sketch-first coverage and any retained direct-Wire exceptions;
- copied, inferred, and fitted parameters;
- replay and BREP validity;
- volume, area, centroid, and bounds errors;
- strict missing/excess material or timeout status;
- diagnostics used and unresolved differences;
- paths to all artifacts.

Never call an approximation `exact_brep` or `geometry_equivalent`.
