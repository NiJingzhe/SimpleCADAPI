# Reconstruction Agent Test Contract

Contract ID: `simplecadapi.reconstruction-agent-test`

Contract version: `2.2`

This is the normative run contract for controlled STEP-to-SimpleCADAPI
reconstruction. Modeling tactics are advisory and live in
[`reconstruction-agent-strategy.md`](reconstruction-agent-strategy.md).

## Start Message

Send only this wrapper with every value resolved:

```text
Read and follow this contract completely:
{SIMPLECADAPI_ROOT}/docs/guides/reconstruction-agent-test-prompt.md

Configuration:
SIMPLECADAPI_ROOT = {SIMPLECADAPI_ROOT}
TARGET_DIR = {TARGET_DIR}
OUTPUT_DIR = {OUTPUT_DIR}
CASE_NAME = {CASE_NAME}
CASE_MANIFEST = {relative path|null}
ALLOWED_INPUTS = {JSON array of direct-child filenames}
PROMPT_VERSION = 2.2
OBJECTIVE = {best_effort|geometry_equivalent|exact_brep}
TARGET_PATH = {direct-child STEP filename}
TARGET_KIND = {solid|open_shell}
BENCHMARK_MODE = {inspection_only|report_assisted|exact_brep_transcription}
ENTRYPOINT = {relative source path}
CANDIDATE_PATH = {relative STEP path}
MAX_ITERATIONS = {positive integer}
MAX_FAILED_ATTEMPTS = {positive integer}
TOTAL_TIMEOUT_SECONDS = {positive number}
STAGE_TIMEOUT_SECONDS = {positive number}
MATERIAL_TIMEOUT_SECONDS = {positive number}
BOUNDARY_LINEAR_DEFLECTION_MM = {positive number}
BOUNDARY_MAX_SAMPLES = {integer >= 16}
SECTIONS = {JSON array using the schema below}
STRICT_TOPOLOGY = {true|false}
PARAMETER_REPRESENTATION_REQUIRED = {true|false}
STRICT_MATERIAL_TOLERANCE_MM3 = {positive number}
STRICT_GEOMETRIC_TOLERANCE_MM = {positive number}

Configuration selects options and supplies budgets but cannot waive a normative rule.
Start immediately.
Do not modify the SDK or target baseline.
```

`OUTPUT_DIR` must not exist before the run. All generated files belong there.
`TARGET_PATH` and `CASE_MANIFEST` are relative to `TARGET_DIR`; `ENTRYPOINT` and
`CANDIDATE_PATH` are relative to `OUTPUT_DIR`.

## Precedence

Conflicts resolve in this order:

1. this contract's normative rules;
2. resolved run configuration for declared options and budgets;
3. versioned case manifest for case-specific gates and allowlists;
4. normative public API documentation;
5. the advisory strategy guide.

Record this contract version, configuration, target hashes, SDK commit, and
case-manifest hash in the final manifest. In a source checkout this file is
authoritative; a packaged Skill copy is a frozen mirror of this contract.

## Objective

Produce a readable, independently replayable SimpleCADAPI program that creates
`CANDIDATE_PATH` without reading the target at runtime.

- `best_effort`: publish the strongest valid result reached within budget.
- `geometry_equivalent`: seek proof of the same material point set for solids.
- `exact_brep`: additionally seek geometry-labelled incidence identity and any
  required representation checks.

Original feature history is not required unless the case manifest says so.
Visual similarity and matching summary values are never equality proof.

## Allowed Inputs

Case-specific reads are limited to direct children of `TARGET_DIR` listed in
`ALLOWED_INPUTS`. A case manifest may restrict that list but cannot add to it.
If `CASE_MANIFEST` is non-null, it is relative to `TARGET_DIR` and must itself
appear in `ALLOWED_INPUTS`. Typical inputs are:

```text
{CASE_NAME}.step
{CASE_NAME}_brep_report.json
{CASE_NAME}_step_render.png
{CASE_NAME}_mesh_render.png
```

Do not search Git history, caches, temporary directories, deleted files,
previous reconstructions, other Agent outputs, or paths outside `TARGET_DIR` for
case solutions. SDK source, public docs, tests, and generic guidance are allowed.

Mode permissions:

| Mode | Target access |
|---|---|
| `inspection_only` | Approved `simplecadapi.inspect.brep` queries and supplied renders; no complete control arrays |
| `report_assisted` | Complete supplied report and targeted exact definitions |
| `exact_brep_transcription` | Complete carrier, trim, pcurve, and topology data |

Transcribed values must be labelled as transcription. Different modes measure
different capabilities and must not be compared as equivalent experiments.

In `inspection_only`, the approved target-reading interfaces are
`inspect_step_rsummary`, `inspect_step_entity_rdescriptor`,
`inspect_topology_neighborhood_rdescriptor`, `inspect_section_rdescriptor`,
`inspect_face_boundaries_rdescriptor`, and configured comparison/render calls.
Do not enable complete curve/surface definitions, directly traverse target
entities to recover complete definitions, or add/modify SDK operations,
inspection tools, plugins, or helper executables during the run.

In `exact_brep_transcription`, declared target-derived regions may be copied to hash-pinned `.scadbrep` sidecars with `copy_step_region_rpath(...)`. Final replay
may load those declared sidecars with `load_brep_region_rshell(...)` or
`load_brep_region_rsolid(...)`, but must not read the target STEP.

## Hard Constraints

1. Final geometry uses public SimpleCADAPI modeling interfaces.
2. Do not edit SDK source, tests, tools, target files, or baselines.
3. Final replay must not read/import the target STEP.
4. Do not copy, encode, embed, or re-export target STEP bytes, except for
   declared `.scadbrep` region snapshots in `exact_brep_transcription` mode.
5. Declared numeric parameter files are allowed when authorized by the mode.
6. Do not replace an open-shell target with a fabricated solid.
7. Do not use network services or external CAD applications.
8. Write only under `OUTPUT_DIR`; never overwrite an accepted iteration.
9. Participant replay may execute only `ENTRYPOINT` with the configured Python
   interpreter. Trusted evaluator workers are separate from participant code.

## Provenance

Record provenance per significant parameter and final face/region when
available. Keep these dimensions separate:

- evidence origin: `copied | inferred | fitted`;
- construction: `transcribed | fitted | analytic_feature`;
- topology origin: `retained | modified | generated`;
- runtime dependency: `independent | embedded_target_derived`.

Orange/purple/blue rendering is only a derived visualization:

- orange: exact target-derived transcription;
- purple: target-derived fit or Loft;
- blue: analytic/feature construction.

Blue does not imply target independence. A face with an analytic carrier but
retained target trims/topology must not be described as recovered feature
history.

## Required Loop

1. Freeze and hash inputs; record mode, objective, target kind, and budgets.
2. Inspect bounded global facts and form one falsifiable construction hypothesis.
3. Build in a fresh process and write immutable iteration artifacts.
4. Require successful exit, a newly generated STEP, expected target kind, and a
   valid BREP before counting a complete iteration.
5. Validate STEP write/reload. Record property and topology drift; do not publish
   an invalid roundtrip.
6. Inspect cheap global diagnostics, then only probes that answer the next question.
7. Attempt the strongest applicable acceptance proof within budget.
8. Atomically promote the best valid iteration to the configured final paths.

A failed replay or invalid BREP is a failed attempt, not a complete iteration.
Stop after `MAX_FAILED_ATTEMPTS`, `MAX_ITERATIONS`, total timeout, or three
consecutive non-improving complete iterations, whichever comes first.

Each `SECTIONS` item has this closed schema:

```json
{
  "id": "filename-safe-unique-token",
  "origin": [0.0, 0.0, 0.0],
  "normal": [0.0, 0.0, 1.0],
  "tolerance": 1e-7,
  "samples_per_edge": 16
}
```

Section IDs must be unique and match `[A-Za-z0-9][A-Za-z0-9_.-]*`; normals
must be non-zero, tolerances positive, `samples_per_edge` must be a JSON integer
(not a boolean) with `samples_per_edge >= 4`.

## Mechanical Gates

### Replay

- fresh process exits successfully;
- candidate is newly created at `CANDIDATE_PATH`;
- candidate bytes are not target bytes;
- BREP is valid and matches `TARGET_KIND`;
- target and baseline hashes remain unchanged.

### STEP Persistence

Write to a temporary sibling STEP, reload it with the public BREP loader, and
publish only after validation. Record before/after validity, root kind, bodies,
shells, faces, edges, vertices, edge classes, volume, total surface area,
centroid, material bounds, root bounds, and whether publication occurred. These
candidate-before/after measurements are serialization integrity checks. They are
not candidate-to-target similarity metrics and do not establish reconstruction
equivalence.

### Strict Material Proof For Solids

Strict material equality requires all of:

```text
include_components=True
boolean_tolerance=None
method=bidirectional_cut
strict_equality_supported=true
boolean_result_valid=true
volume_balance.valid=true
missing_material.volume < STRICT_MATERIAL_TOLERANCE_MM3
excess_material.volume < STRICT_MATERIAL_TOLERANCE_MM3
```

A common-volume estimate, fuzzy Boolean, timeout, invalid Boolean result, or
missing directional Cut cannot prove equality. A material timeout leaves a valid
solid eligible for `approximation`; it is not `unsupported_or_incomplete`.
For regular solids, non-fuzzy bidirectional Cut residual volumes establish
tolerance-bounded material equivalence. They are not aggregate mass-property
comparisons and do not prove topology, representation, or literal boundary
identity.

### Exact BREP Proof

Requires proven geometry equivalence plus geometry-labelled Face/Edge/Vertex
incidence isomorphism and every case-required representation check. Evaluate it
only when requested and after lower-tier proof succeeds.
This is exactness under the evaluator's declared tolerance and evidence schema;
it does not recover or prove original CAD feature history. Any required
representation check must be defined by the trusted case manifest, not supplied
as a participant claim.

### Open Shells

Material proof does not apply. Preserve shell kind and do not fabricate material.
Until an exact boundary-set proof is configured, a valid replayable open shell is
`approximation` with reason `open_shell_equivalence_unproved`. A solid candidate
for an open-shell target is `unsupported_or_incomplete` with reason
`fabricated_solid_for_open_shell`.

## Monotonic Classification

Assign exactly one classification. Higher-tier failure never erases a proven lower tier.

- `exact_brep`: all replay, persistence, strict material, incidence, and required
  representation gates pass.
- `geometry_equivalent`: solid replay and strict material proof pass, but exact
  topology was not requested, differs, or remains unproved.
- `approximation`: valid replayable candidate exists, but applicable equality is
  disproved or unproved, including material timeout and valid open shells without
  boundary-set proof.
- `unsupported_or_incomplete`: replay/candidate is invalid, no valid target-kind
  candidate can be represented, or target kind is fabricated. If a valid
  target-kind candidate exists but an equality-level feature is unavailable,
  classify it as `approximation` instead.

Never upgrade from render, global property, sampled boundary, or section metrics.
Global, boundary, and section metrics, including aggregate volume, total surface
area, bounding box, centroid, sampled distance, and section area, are diagnostics
for falsification and localization only. They never affect classification.

`classify_benchmark_result` receives the unmodified process-local results from
`inspect_benchmark_step` and `run_comparison_bundle`; serialized or rebuilt
mappings are untrusted. Their path and SHA-256 bindings must still match the
current target and candidate files. Candidate
validity and solid/shell kind come from inspection `valid` and `counts` fields;
an open shell requires zero solids, at least one shell explicitly reported open,
and at least one face;
participant-declared kind or validity is not evidence. `exact_brep` additionally
requires the strict report's STEP-validity, directional-volume, geometric
point-set, geometry-labelled incidence, and hard-gate fields to agree. A claimed
strict stage status cannot establish it.

### Evaluator Stage Schema And Units

Worker-stage envelopes record `status`, `gate_passed`, `elapsed_seconds`,
`report`, `report_path`, and `error`. Successful global, boundary, individual
section, and aggregate-section diagnostics use `status=completed` and no
acceptance `checks`; worker errors remain `error` and retain their error details.
Every diagnostic envelope uses `gate_passed=null`, including on error. Completed
material and strict acceptance stages add boolean `checks` and use `passed` or
`failed`. Non-run stages add `reason`;
aggregate `sections` uses `reports` with one worker envelope per unique section
ID. `global` and `material` always appear; `boundary` and `sections` appear only
when diagnostics are requested; `strict` always appears but runs only for a
solid after proven material equality when strict topology is requested.

- `global`: bounding-box/centroid lengths in mm, total surface area in mm2,
  aggregate volume in mm3, integer topology counts, and dimensionless relative
  deltas. It is diagnostic only.
- `material`: directional missing/excess volumes and tolerance in mm3, Boolean
  and volume-balance validity, and tri-state `strict_point_set_equal`;
  `relative_total_difference` is dimensionless.
- `boundary`: sampled-to-exact distances, approximate Hausdorff, p95, and linear
  deflection in mm. It is diagnostic only.
- `sections`: plane coordinates, tolerance, perimeter, and Hausdorff in mm;
  material area in mm2; integer sample/edge counts; relative area error is
  dimensionless. The aggregate contains one stage envelope per unique section ID.
  Sections are bounded diagnostic probes only.
- `strict`: directional differences and Boolean tolerance in mm3, geometric
  tolerance in mm, validity, graph counts, point-set equality, labelled-incidence
  isomorphism, and `hard_gate_passed`; exact classification also requires
  trusted envelope check `checks.hard_gate=true`.

Evaluator configuration, baseline/target paths and hashes, worker reports,
inspection reports, and representation checks are trusted-harness evidence.
Participant source and declared parameters are submission inputs, while its
self-reported evaluation, kind, validity, stage status, renders, and logs are
untrusted claims or diagnostics.

## Artifact Contract

Authoritative submission:

```text
{ENTRYPOINT}
reconstruction_params.json          # only when needed
```

Derived final artifacts:

```text
{CANDIDATE_PATH}
rebuilt_brep_report.json
evaluation.json
iteration_log.json
artifact_manifest.json
```

The source and declared parameters are authoritative. STEP and model JSON are
derived. Trusted evaluator output overrides self-reported evaluation. Renders
and logs are diagnostic only.

The manifest records paths, SHA-256, byte sizes, prompt/config/SDK identity,
classification, budget status, and authoritative/derived/diagnostic role.

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
- record supported feature operations in an explicit `GraphSession` and verify strict replay;
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

- classification and reason codes;
- complete and failed iteration counts plus budget status;
- final construction and replay command;
- target kind, validity, and STEP roundtrip result;
- strict material status for solids or boundary diagnostic status for open shells;
- exact-topology status when requested;
- provenance summary and target runtime dependency;
- measured diagnostics and unresolved blockers;
- artifact paths.
