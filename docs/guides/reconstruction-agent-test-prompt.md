# Reconstruction Agent Test Contract

Contract ID: `simplecadapi.reconstruction-agent-test`

Contract version: `2.1`

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
PROMPT_VERSION = 2.1
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
GLOBAL_MAX_BBOX_DELTA_MM = {non-negative number}
GLOBAL_MAX_CENTROID_DISTANCE_MM = {non-negative number}
GLOBAL_MAX_RELATIVE_VOLUME_ERROR = {non-negative number}
GLOBAL_MAX_RELATIVE_AREA_ERROR = {non-negative number}
BOUNDARY_LINEAR_DEFLECTION_MM = {positive number}
BOUNDARY_MAX_SAMPLES = {integer >= 16}
BOUNDARY_MAX_HAUSDORFF_MM = {non-negative number}
BOUNDARY_MAX_P95_MM = {non-negative number}
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

In `exact_brep_transcription`, declared target-derived regions may be copied to
hash-pinned `.scadbrep` sidecars with `copy_step_region_rpath(...)`. Final replay
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
6. Run cheap global checks, then only diagnostics that answer the next question.
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
  "samples_per_edge": 16,
  "require_nonempty": true,
  "max_hausdorff": 0.1,
  "max_relative_area_error": 0.01
}
```

Section IDs must be unique and match `[A-Za-z0-9][A-Za-z0-9_.-]*`; normals
must be non-zero, tolerances positive, `samples_per_edge` must be a JSON integer
(not a boolean) with `samples_per_edge >= 4`, and `require_nonempty` must be a
JSON boolean.

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
shells, faces, edges, vertices, edge classes, volume, area, centroid, and
whether publication occurred.

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

### Exact BREP Proof

Requires proven geometry equivalence plus geometry-labelled Face/Edge/Vertex
incidence isomorphism and every case-required representation check. Evaluate it
only when requested and after lower-tier proof succeeds.

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
`report`, `report_path`, and `error`. Completed comparison stages add boolean
`checks`; non-run stages add `reason`; aggregate `sections` uses `reports` with
one worker envelope per unique section ID. Status is `passed`, `failed`,
`error`, `skipped`, or `not_applicable`. `global` and `material` always appear;
`boundary` and `sections` appear only when diagnostics are requested; `strict`
always appears but runs only for a solid after proven material equality when
strict topology is requested.

- `global`: bounding-box/centroid lengths in mm, area in mm2, volume in mm3,
  integer topology counts, and dimensionless relative deltas.
- `material`: directional missing/excess volumes and tolerance in mm3, Boolean
  and volume-balance validity, and tri-state `strict_point_set_equal`;
  `relative_total_difference` is dimensionless.
- `boundary`: sampled-to-exact distances, approximate Hausdorff, p95, and linear
  deflection in mm. It is diagnostic only.
- `sections`: plane coordinates, tolerance, perimeter, and Hausdorff in mm;
  material area in mm2; integer sample/edge counts; relative area error is
  dimensionless. The aggregate contains one stage envelope per unique section ID.
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

## Final Response

Report concisely:

- classification and reason codes;
- complete and failed iteration counts plus budget status;
- final construction and replay command;
- target kind, validity, and STEP roundtrip result;
- strict material status for solids or boundary-proof status for open shells;
- exact-topology status when requested;
- provenance summary and target runtime dependency;
- measured diagnostics and unresolved blockers;
- artifact paths.
