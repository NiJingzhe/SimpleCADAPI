# Workflow: Single-Part Modeling

Model one physical part from confirmed requirements to validated, optionally
packaged geometry. The workflow is role-structured. Roles 1 and 2 establish
the requirements and the stage plan; Roles 3 and 4 then run a strict,
stage-by-stage TDD loop; Role 5 exports only after every stage gate passes.

Standing discipline, binding for every role:

- **Serial stages, no bundling.** Do not prepare a later stage's model or
  verification artifact early. Finish the current stage gate before entering
  the next `S` stage.
- **Verifier before model.** For every stage, define and exercise the
  verification contract before editing the real part source. A model is not
  accepted because it builds; it is accepted only when the prepared checks
  pass.
- **⛔ BLOCKING means stop.** At a blocking gate, wait for the explicit user
  answer. Never decide on the user's behalf.
- **Image judgments are delegated.** Visual checks are planned by Role 3
  before the stage model is built; the render may be produced by Role 4
  afterward, but its acceptance verdict is supplied by an isolated subagent.
- **Repair the owning artifact.** A failed verification reopens the current
  stage's verifier contract or model, whichever owns the failure. Never patch
  downstream symptoms or weaken a check to pass it.

## Role map

| # | Role | Reads (load before acting) | Produces | Exit gate |
| --- | --- | --- | --- | --- |
| 1 | Requirement Confirmer | `domains/requirement-refinement.md`, `discipline/requirement-and-cad-brief.md` | `<part-dir>/REQUIREMENTS.md` | ⛔ user consent received |
| 2 | Master Planner | `REQUIREMENTS.md`, `discipline/mechanical-modeling.md`, `discipline/datums-and-coordinate-systems.md` | `<part-dir>/BUILD_PLAN.md` + base TODOs | plan presented |
| 3 | Verifier Planner | `REQUIREMENTS.md`, `BUILD_PLAN.md`, `discipline/geometric-validation.md`, exact API/diagnostic pages used by the check | current-stage verification contract, hypothesis snippets, executable verification script, `plan verifier` and `run verifier` TODO items | verification artifact is ready before modeling |
| 4 | Detail Modeling Planner & Builder | current stage's verifier contract, `domains/part-modeling.md`, `discipline/feature-ordering.md`, exact modeling API pages | current-stage model, operation hypotheses, rendered evidence inputs | model runs and the prepared verifier passes |
| 5 | Exporter | `REQUIREMENTS.md` export rows, `domains/export-and-translation.md`, `domains/assembly-and-product.md` | `.scadpkg` + requested exports, readability check | artifacts re-open cleanly |

## Role-switch protocol

Before starting a role's work, output exactly:

```markdown
## [Role Switch: <Role Name>]
Reading: <role-owned files>
Artifact out: <path>
```

Then act only inside that role's scope. Roles 3 and 4 switch for each
Master-Planner stage as follows:

```text
S1: Role 3 plan verifier -> Role 4 build -> Role 3 run/review verifier
S2: Role 3 plan verifier -> Role 4 build -> Role 3 run/review verifier
...
Sn: Role 3 plan verifier -> Role 4 build -> Role 3 run/review verifier
```

Role 3 may use hypotheses to design a check, but may not certify a model it
has not tested. Role 4 may use modeling hypotheses, but may not start a stage
until that stage's verification contract and script exist. A failed stage does
not advance the TODO; it appends or starts a `repair:` item for the owning
artifact and repeats the same Role 3/4 loop.

---

## Role 1 — Requirement Confirmer ⛔

Convert the request into `REQUIREMENTS.md`. No geometry, no probe builds,
no source-file writes before this role's gate closes.

Procedure:

1. Classify inputs (prose / reference images / drawings / mesh models ,etc.). For any image
   containing reference structure: write the interpreted shape region by
   region — overall form, visible features and locations, symmetry and
   orientation, anything hidden or uncertain. **Describing is not
   confirming:** the interpretation ends as part of ONE batched `ask` that
   also covers the Ask-or-Record blocking table
   (`domains/requirement-refinement.md`). Shape-level facts are always
   confirmed; only dimension-level defaults may be assumed once a scale
   anchor exists.
   For provided models(most cases are mesh), use python code to render and inspect geometry information through something like sampling / fitting, which may provide useful geometry information for you to build similar stucture / rebuild same struction in brep through simplecadapi.
2. For undetermined parameters / geometry / function / performance, propose
   recommended assumptions as ask options (default first) so the user can
   accept or override in one round.

<!-- skill:if omp -->

### Host binding: designing the Role 1 `ask` payload (omp)

OMP already provides and executes the `ask` tool. This block defines only how
to design its input for the Requirement Confirmer. After writing the
region-by-region interpretation and the Ask-or-Record ledger, make one batched
call for all unresolved items that can block `REQUIREMENTS.md`.

Design each question so its answer can be copied into one ledger row:

- Ask about one decision, not one vague topic. Name the affected region,
  feature, axis, or interface and state the evidence or ambiguity.
- Ask shape-level interpretation explicitly. Do not hide a disputed region in
  a general "does this look right?" question.
- Separate independent decisions such as overall orientation, hole axis,
  thread representation, and mounting intent. Use `multi: true` only when the
  user may independently select several items from the same set.
- Make options mutually exclusive and operational: each option must say what
  will be recorded and what modeling consequence follows. Do not offer
  imaginary precision that the source does not support.
- Put the conservative, clearly labeled assumption first and set
  `recommended: 0`; this is a recommendation, never consent. Include a
  concrete correction path in the options so the user can reject or amend the
  interpretation.
- Ask only blocking decisions in this round. Record inferable dimensions and
  low-risk defaults as assumptions with their basis; do not burden the user
  with API or verification choices owned by later roles.

Example payload shape (the actual labels and questions must be derived from the
current part, not copied literally):

```ts
ask({
  questions: [
    {
      id: "region_c_flange_location",
      question: "The drawing leaves the C-view flange location ambiguous. Which region is the C flange?",
      options: [
        { label: "The -Y horizontal-port end", description: "Record C as the long rounded flange on the -Y end; model its axis along Y." },
        { label: "The top vertical-bore end", description: "Record C as the flange around the top vertical bore; revise the region map before modeling." }
      ],
      recommended: 0
    },
    {
      id: "thread_representation",
      question: "The drawing calls out M36-6H, but does not establish whether thread faces are needed for this deliverable. How should it be represented?",
      options: [
        { label: "Nominal bore", description: "Record the callout and model the nominal bore; do not create helical faces." },
        { label: "Explicit thread geometry", description: "Record modeled thread geometry as required and plan a thread-specific verification." }
      ],
      recommended: 0
    },
    {
      id: "mounting_intent",
      question: "What mounting intent should the base holes represent?",
      options: [
        { label: "Through-bolted to a flat base", description: "Record insertion along Z and verify the fastener envelope and underside clearance." },
        { label: "Tapped or blind mounting", description: "Record the hole termination and thread requirement; do not assume through holes." }
      ],
      recommended: 0
    }
  ]
})
```

Use stable machine-readable `id` values that match ledger rows. After the call,
copy the returned selected options, custom answers, notes, and any timeout
status into `REQUIREMENTS.md`; preserve the user's wording for corrections.
The gate closes only when every blocking row has an explicit answer or an
explicitly recorded assumption permitted by the requirement discipline. A
recommendation or timeout is not user consent. On cancellation, incomplete
answers, or unavailable interactive UI, keep the gate blocked and stop; never
continue by silently selecting the recommended option.

When a question has no valid answer among the proposed options, its wording
must make clear what correction or missing requirement the user should supply.
Do not ask the user to choose an implementation detail owned by a later role;
ask only for the requirement that changes the model or its acceptance criteria.

<!-- skill:endif -->
3. Fastened or load-bearing parts: the requirements contain the envelope
   arithmetic, not just values — head diameter + shaft + wall/clearance →
   minimum land diameter, boss thickness, edge distance, and lateral
   offset along the insertion path.
4. Write `REQUIREMENTS.md`:

```markdown
# Requirements: <part name>
- Inputs: <prose | images used | drawings>
- Functional goals: <what the part must do>
- Geometry targets: <confirmed shape description, region by region>
- Units / coordinate convention: <mm; origin, base plane, up axis>
- Named parameters (Var): <name = value | ASSUMED default>
- Fastening & mounting: <fastener, axis, head side, insertion path>
  Envelope math: <head+shaft+wall -> min land / boss / offset>
- Service conditions: <load direction and class | none stated>
- Export targets: .scadpkg always; STEP/STL/OBJ/MJCF/FCStd if requested
- Verification intent: <what the user's words require proving>
- Ask-or-Record ledger: | item | asked/assumed | answer/value |
```

Gate: the `ask` returned answers, consent is recorded in the ledger, and
`REQUIREMENTS.md` exists. Entering Role 2 without this gate is the cardinal
violation.

## Role 2 — Master Planner

From `REQUIREMENTS.md` only — no API detail, no step-level modeling.

1. Choose the construction strategy (profile-driven vs block-and-feature)
   and fix the datum from the functional interface; one-paragraph rationale
   each.
2. Design the construction as numbered stages `S1..Sn`. For each stage state
   exactly what new substructure is complete at its output boundary and what
   later stages are not yet included. Pair every stage with its future
   verification target, but leave the executable verification design to Role
   3.
3. Write `BUILD_PLAN.md` with the stage output boundaries, datum, intended
   construction strategy, and the requirement-to-stage mapping. Role 3 adds
   verification contracts and Role 4 adds modeling hypotheses and source
   details while the loop runs.
4. Initialize the TODO tool with phases `Requirements / Plan / Build & Verify /
   Export`. For each stage create stable `plan verifier`, `model`, and `run
   verifier` items. The `run verifier` item is completed only after Role 3 has
   executed the prepared check against the Role 4 result. Mark Requirements
   done, Plan done, and start the first stage's `plan verifier` item.

Present the plan in ≤10 lines. No approval gate; enter the Role 3/4 loop.

<!-- skill:if omp -->

### Host binding: TODO tool (omp)

Tool name: `todo`. Operations: `init(list=[{phase, items[]}])`,
`start(task)`, `done(task|phase)`, `drop(task|phase)`, `block(task, reason)`,
`unblock(task)`, `append(phase, items[])`, `rm`, `view`. Contract: batch
`todo` calls together with real work in the same turn; task strings are stable
identifiers — quote them exactly when completing. Keep the current stage's
`model` item pending until its `plan verifier` artifact exists. A failed
`run verifier` reopens the owning verifier or model through a `repair:` item;
never advance the stage while either owner is open.

<!-- skill:endif -->

## Role 3 — Verifier Planner

Role 3 runs before every stage's modeling work and owns the stage's
verification contract. It is the modeling equivalent of writing tests before
implementation.

For the current `S` stage, in order:

1. Identify the stage output: name the substructure that must be complete,
   its datum/coordinate relationship, and the existing geometry it may touch.
   State what is deliberately out of scope until later stages.
2. Translate the requirements into acceptance criteria for that output:
   dimensions and tolerances; required faces, holes, axes, or features;
   interfaces and fit with already-built geometry; collision and clearance;
   fastener insertion and tool access; assembly reachability; demolding or
   manufacturing access when relevant; absence of unintended interference;
   BREP validity and single-solid expectations. Include visual criteria when
3. Turn every criterion into a deterministic check. Iterate through small
   hypothesis code snippets or probes in the available execution environment:
   deliberately good and bad probes must show that the proposed measurement,
   collision test, topology query, or visual review contract distinguishes pass
   from fail. Reject a check that merely prints a plausible value without
   testing the requirement.
4. Produce the executable verification script or function for this stage,
   including explicit pass/fail assertions, named measurements, and small
   evidence prints. Append to `BUILD_PLAN.md`:
   `Verifier contract: <output> / Criteria: <...> / Script: <path or symbol>`
   plus the hypothesis results and known-bad proof.
5. Update TODO before modeling: complete the current `plan verifier` item
   after the contract, executable check, hypothesis evidence, and known-bad
   proof are recorded. The `model` item may then start. After Role 4 produces
   the stage result, start `run verifier` and execute the exact prepared
   function or script against that result; only its passing output closes the
   stage.

Role 3 may prepare visual verification here. It defines named render views,
close-ups, comparison regions, and the structured verdict required from an
isolated reviewer. It does not treat a render it produced as its own visual
acceptance.

<!-- skill:if omp -->

### Host binding: persistent REPL and TODO state machine for Verifier Planner (omp)

Use the persistent `eval` tool (language `py`) for hypothesis snippets and
known-bad probes. Keep setup, hypothesis, and final check cells incremental;
do not hide an unproven check in a temporary one-shot script. Use `todo` to
make the current stage's verification contract a real gate, not a note.

Role 2 creates the stable stage tasks in the `Build & Verify` phase. For each
stage, the initial task order is:

```text
S1 plan verifier
S1 model
S1 run verifier
S2 plan verifier
S2 model
S2 run verifier
...
```

Use the exact task strings consistently. When Role 3 enters a stage, start its
`plan verifier` task:

```text
todo(op="start", task="S1 plan verifier")
```

If a stage was added after the original initialization, append all three tasks
as one ordered batch before starting the first one:

```text
todo(op="append", phase="Build & Verify", items=[
  "S3 plan verifier",
  "S3 model",
  "S3 run verifier",
])
todo(op="start", task="S3 plan verifier")
```

Do not append a later stage's tasks while the current stage is still open. A
repair item for the current stage is the exception: append it next to the
owning task and keep the stage open.

After the verifier contract, executable check, hypothesis evidence, and
known-bad proof are recorded in `BUILD_PLAN.md`, close the planning gate and
open the modeling gate in the same work turn:

```text
todo(op="done", task="S1 plan verifier")
todo(op="start", task="S1 model")
```

Role 4 owns the model task. It must not start before the `plan verifier` task
is done. After Role 4's source run completes, Role 4 closes `S1 model` and
starts `S1 run verifier`; Role 3 then executes the exact prepared function or
script named in that task.

On a passing verification, record the output/evidence and close the gate:

```text
todo(op="done", task="S1 run verifier")
```

Only then may Role 3 start `S2 plan verifier`. On a failed check, do not call
`done`, `drop`, or rewrite the acceptance criterion merely to clear the list.
Identify the owner and append a stable repair task in the same phase, for
example:

```text
todo(op="append", phase="Build & Verify", items=[
  "repair: S1 verifier collision check",
])
todo(op="start", task="repair: S1 verifier collision check")
```

If the check is wrong, repair and re-prove the verifier contract; if the model
is wrong, keep the verifier task intact and append a model repair item. After
repair, return to the current stage's `run verifier`; never advance to `S2`.
Use `todo(op="view")` after a repair or interruption to re-ground task text
and status. Batch TODO calls with the real REPL, file, or verification work in
the same turn; keep task strings stable and mark each item done immediately at
its actual gate.

<!-- skill:endif -->

## Role 4 — Detail Modeling Planner & Builder

Role 4 starts only after Role 3's current-stage verifier contract and
executable check exist. It owns the detailed construction of the current
stage, not the acceptance definition.

For the current stage:

1. Read the verifier contract, then choose a construction strategy from the
   geometry and the controlling dimensions. The categories below are a design
   ladder, **not an API whitelist**: select the operations that express the
   current stage's design intent, then read the exact documentation page for
   every operation before its first call. A method absent from its page does
   not exist.

   - **Profile and sketch first when they control the shape.** Analyze the
     required 2D sections, symmetry, datum planes, and dimensional relations.
     Use `make_sketch_rsketch` with the applicable `constrain_*` APIs and
     `inspect_sketch_rsketchresult` when a constrained sketch carries design
     intent; promote it through `make_wire_from_sketch_rwire` or
     `make_face_from_sketch_rface`. Build solids from that intent with
     `extrude_rsolid`, `revolve_rsolid`, `loft_rsolid`, `sweep_rsolid`, or a
     helical sweep when the feature is genuinely helical. A closed profile is
     preferred when its parameters directly represent the requirement.
   - **Primitives are an alternative for genuinely regular base forms.** Use a
     box, cylinder, cone, sphere, or other documented primitive when it maps
     directly to the controlled form; do not force a sketch only because one
     exists. Keep the controlling dimensions as named parameters either way.
   - **Build named feature solids, then combine them deliberately.** Start
     from a named base solid, create each additive boss/rib/flange or
     subtractive bore/pocket/opening as a separately named solid or tool, then
     use `union_rsolid`, `cut_rsolid`, or `intersect_rsolid` to obtain the next
     single Solid. Repeat construct-feature -> Boolean -> verify for each
     required feature group; ensure intentional positive overlap for unions
     and tool overshoot for cuts. Do not assemble an opaque final shape in one
     expression.
   - **Use advanced features only after the prototype feature is proven.**
     Validate one representative feature before `linear_pattern_rsolidlist` or
     `radial_pattern_rsolidlist`; use documented transforms or mirrors for
     symmetry. Apply `fillet_rsolid`, `chamfer_rsolid`, `shell_rsolid`, and
     similar topology-sensitive features after their supporting geometry and
     selectors are stable.
   - **Use surface construction when the requirement is surface-led.**
     Consider documented ruled, patch, Bezier, Gordon, cylindrical, trimmed,
     sewn, or lofted surfaces; turn a closed, valid shell into a Solid only
     when that is the required topology. Do not approximate a freeform or
     transition surface with arbitrary primitives merely because booleans are
     familiar.

2. Name every meaningful construction step before it is used: source variables,
   helper functions, exposed parameters, and tags must identify the part role
   or feature rather than its creation order. Prefer names such as
   `mounting_base`, `port_bore_tool`, `front_flange`, and
   `feature.mounting_bore` over `shape2`, `cut1`, or numeric topology indexes.
   Attach semantic tags with `apply_tag(shape=..., tag=...)`, inspect them with
   `list_tags(shape=...)`, and use tag-aware QL selection where later features
   or verification need stable intent. Use `role.*`, `feature.*`, and `tool.*`
   namespaces; keep numeric facts in metadata rather than tags.

3. Use small hypothesis code snippets or probes in the available execution
   environment to test the proposed construction sequence on minimal solids.
   Print types, counts, volumes, bounds, tag/selection cards, and other facts
   required by the verifier contract. Adopt an operation only when its evidence
   shows that it can produce the required shape. Append
   `Hypothesis: ... / Result: ... / Adopted: ...` under the current stage in
   `BUILD_PLAN.md`.
4. Edit the part source only after the operation hypotheses pass. Use keyword
   arguments, named parameters, role/feature/tool tags, and QL fact prints;
   include selection cards before every fillet/chamfer.
5. Run the source and hand the resulting stage geometry to Role 3. Role 3
   executes the exact prepared verification script. The stage passes only when
   all assertions, measurements, fit/access checks, and required visual
   verdicts pass. A visual verdict comes from the isolated reviewer contract
   planned by Role 3.
5. On failure, do not weaken the check. Determine whether the verifier
   contract or the model owns the defect, add a `repair:` TODO to that owner,
   and repeat Role 3/4 for the same stage. Start the next stage only after the
   current stage's `model` and `run verifier` items are both complete.

<!-- skill:if omp -->

### Host binding: persistent REPL for Detail Modeling Planner & Builder (omp)

Use `eval` (language `py`) for incremental construction hypotheses; names
survive across calls. Keep the real source run in bash. Never use a modeling
success message as the verification result: invoke the prepared verifier
function or script and record its output in the stage evidence.

<!-- skill:endif -->

## Verifier contract patterns

Role 3 selects the applicable checks per stage; it does not mechanically run
every pattern. A contract may combine:

- dimensional measurements with explicit tolerance bounds;
- topology, axis, and face-location queries for required features;
- BREP closure, positive volume, and solid-count checks;
- swept insertion envelopes for screws, tools, or assembly access, with a
  zero-collision criterion;
- clearance and interference checks against already-built substructures;
- demolding or tool-direction access checks when manufacturing intent requires;
- named renders and isolated per-region visual verdicts;
- functional motion or clearance checks when the part has moving interfaces;
- FEM only when service conditions are stated in `REQUIREMENTS.md`.

Every selected pattern needs a deterministic pass/fail condition and a
known-bad hypothesis proof before the current stage is modeled.

<!-- skill:if omp -->

### Host binding: mandatory isolated image review (omp)

When Role 3 selects visual verification, any image-based acceptance judgment
must be executed by a clean-context reviewer. The context that produced a
render cannot certify it. Role 3 defines the visual contract before Role 4
builds: reference/render paths, named views, regions, required verdict fields,
and the reviewer input description.

- Default: spawn one isolated `task` reviewer with file paths and the written
  shape description from `REQUIREMENTS.md`; demand structured per-region
  `match` / `mismatch` / `unreviewable` verdicts with reasons.
- If a standing reviewer peer exists, use `hub` to send the same contract and
  record its reply verbatim.
- A mismatch cannot be overridden by the main context. Repair the owning
  model, render again, and repeat the isolated review.
- If neither reviewer mechanism exists, the visual gate remains open and the
  stage cannot pass.

<!-- skill:endif -->

## Role 5 — Exporter

Read the export rows from `REQUIREMENTS.md`. Durable canonical delivery is
`capture(result, "out/<part>.scadpkg")`; external formats go through
`domains/export-and-translation.md` capabilities. Post-export gate:
re-open the package in a fresh process (`validate_product_package` /
definition materialization) and confirm definition/solid counts; list every
produced file with size.

Final delivery ⛔: evidence pack + artifact list + assumptions made +
checks not run, and record the user's verdict. A rejection here routes back
through the role map to the owning artifact.

---

## Failure routes

- Boolean fails or yields multiple bodies → `domains/part-modeling.md`
  boolean discipline (overlap, overshoot tools, isolate the pair).
- Fillet/chamfer fails → smaller radius, narrower selection, later order;
  selection problems follow the edge-selection defaults.
- Dimension mismatch → re-measure against `REQUIREMENTS.md`; fix the named
  parameter, not the symptom.
- Repeated dead ends → `discipline/failure-and-repair.md`; reconsider the
  BUILD_PLAN stage, not the same retry.

Part source file, `REQUIREMENTS.md`, `BUILD_PLAN.md` with stage output
boundaries, verifier contracts, executable verification scripts, modeling
hypotheses, and method proofs; evidence pack paths; image verdicts quoted
from isolated subagent reviews; package/exports with sizes; assumptions made;
and checks not run.
