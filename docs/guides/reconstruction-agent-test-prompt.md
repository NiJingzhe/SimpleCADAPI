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

The default objective is `geometry_equivalent`, not identical topology or
original feature history. Geometry equivalence means that strict bidirectional
material difference proves the same occupied material point set. Matching
renders, volume, area, bounds, centroid, sections, or topology counts alone is
not proof.

`exact_brep` is optional and must not consume iterations unless explicitly
requested.

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
arrays from the report.

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
informative. The returned groups are descriptive multiplicities only. They do
not prove a pattern.

Use `extract_face_boundaries(compact=true)` before requesting sampled boundary
arrays. Compact mode preserves ordered edge occurrences, orientation, type,
length, endpoints, and key scalar parameters while keeping context small.

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
  evidence says the candidate is close enough to justify a strict proof.
- Bound it by `MATERIAL_TIMEOUT_SECONDS`. A timeout means equivalence remains
  unproved; it does not mean the model is equal.
- Use `compare_boundary_distance` only to diagnose an approximation. Start with
  at most 200 samples and use `target_face_ids`/`current_face_ids` when a local
  region is known.
- `build_difference_regions` defaults to Boolean material components. Reuse an
  existing `material_result`; include boundary clustering only when needed and
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
3. Run `compare_global_properties`.
4. If global/material scale is clearly wrong, fix the construction before any
   dense boundary or topology work.
5. Use sections or local diagnostics only to answer the next modeling question.
6. When the candidate is plausibly final, attempt one bounded strict
   `compute_material_difference`.

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

Requires fresh replay, valid BREP, strict bidirectional material equality,
geometry-labelled incidence graph isomorphism, and required representation
checks. Only evaluate this when explicitly requested.

### geometry_equivalent

Requires fresh replay, valid BREP, and strict bidirectional material equality.
Boundary, section, seam, surface representation, and topology equality are not
additional requirements.

### approximation

Use when a valid replayable candidate exists but strict material equality
fails or remains unproved, including Boolean timeout. Report measured global
and local errors without upgrading the result based on visual similarity.

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
- copied, inferred, and fitted parameters;
- replay and BREP validity;
- volume, area, centroid, and bounds errors;
- strict missing/excess material or timeout status;
- diagnostics used and unresolved differences;
- paths to all artifacts.

Never call an approximation `exact_brep` or `geometry_equivalent`.
