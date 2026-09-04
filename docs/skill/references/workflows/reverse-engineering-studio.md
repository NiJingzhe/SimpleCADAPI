# Workflow: Reverse-Engineering Studio (human-in-the-loop)

Drive the interactive reconstruction studio (`viewer/` re-mode) as the agent
side of a two-actor loop: a human annotates the STEP target in the browser,
the agent reconstructs from those annotations, and the browser displays the
artifacts for the next refinement round.

## Goal and scope

Use when a human operator is available to supply feature intent for a STEP
target — the variable that pure LLM+inspection reconstruction cannot recover
from geometry alone. The human selects faces, draws regions, and labels
intent (`sketch_base`, `revolve_axis`, `pattern_seed`, `fillet_group`,
`exact_copy`, free text); the agent turns each submission into FTC code and
verification artifacts.

Not for fully autonomous reconstruction — that path stays in
`step-reconstruction.md` with no UI dependency.

## Hard rules

- **Only the human's browser writes `re_work/submission.json`.** The agent
  must never POST `/api/submit` or author the submission file; the submission
  is the ground-truth human signal and the training record depends on it being
  genuine.
- The agent writes artifacts; it does not edit geometry in the UI. The UI has
  no geometry-editing surface — code is the single source of truth.
- Verification stays external to the modeling scripts (same rule as
  everywhere else): run verifiers and comparison renders as separate steps.

## Session layout

```text
<case_dir>/
  target.step
  re_work/
    annotations.jsonl    # append-only annotation events (UI authoritative)
    submission.json      # atomic handoff: annotations + server-side context
    submission.seq
    session.ndjson       # full event recording (selections, resolves, submits,
                         # artifact versions) — the training-data side channel
    snapshots/snap-N.png # viewport snapshot submitted with round N
    rebuild.py           # agent artifact: FTC reconstruction source
    rebuilt.step
    rebuilt.scadpkg      # captured v3 product package (loads in the UI)
    comparison.png       # render_step_comparison_rpath shared-camera diff
    evaluation.json      # external verification report
```

`submission.json` carries, per annotation: canonical entity ids
(`face:12`), the intent label, free text, the screen polygon, and a
server-composed context card per entity (`describe_entity` geometry, bounds,
capped adjacency) plus the global target summary. Unresolvable entity ids are
listed in `unresolved_entity_ids` — treat them as data errors, not silently
dropped input.

## Loop

1. Start the studio and hand the URL to the operator:

   ```bash
   uv run python -m viewer.server <case_dir> --daemon
   ```

   The detached server binds `127.0.0.1:7170` (lockfile
   `<case_dir>/.re_server.lock`), builds the scene in the background, and
   opens `http://127.0.0.1:7170/re.html` (built frontend from `viewer/dist`;
   during development run `npm run dev` in `viewer/`, which proxies `/api`).

2. Block on the first submission (stay under the Bash tool timeout):

   ```bash
   uv run python -m viewer.server <case_dir> --wait-only --timeout 590
   ```

   Exit 0 = fresh submission; 124 = timeout (re-check `re_work/submission.json`
   once before falling back to chat); 1 = server died (restart with
   `--daemon`, the browser tab reconnects).

3. Read `re_work/submission.json`. Reconstruct per the reconstruction
   contract (`docs/guides/reconstruction-agent-test-prompt.md`): FTC feature
   blocks, external verification, tiered acceptance. Annotations are intent
   hints, not geometry truth — an `exact_copy` region still needs measured
   parameters or `copy_step_region_rpath` transcription.

4. Write the artifact set into `re_work/` (names are fixed — the UI polls
   them): `rebuild.py`, `rebuilt.step`, `rebuilt.scadpkg` (via `scad.capture`),
   `comparison.png` (via `render_step_comparison_rpath`), `evaluation.json`.

5. Loop to step 2 for the next refinement round. Finish with:

   ```bash
   uv run python -m viewer.server <case_dir> --shutdown
   ```

## Data output

`re_work/session.ndjson` is the training record: every selection, region
resolve, annotation event, submission, and artifact version, with
timestamps. Keep it alongside the artifact set when harvesting cases; it is
the trajectory, not just the endpoint pair.
