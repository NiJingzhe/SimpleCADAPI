# Workflow: Engineering Drawing Generation

Produce a GB-standard engineering drawing sheet set (DXF + PNG) from an
already-validated part or product. This is a preliminary, deliberately simple
workflow: drawing is an output stage, so geometry must be final before entry.
It composes one domain — `domains/engineering-drawing.md` — and does not
repeat its solver rules; read that domain first.

Standing discipline, binding for every stage:

- **Geometry first, drawing second.** Enter only with validated geometry and
  a settled datum story. A drawing never repairs a model; it exposes one.
- **Declare, never position.** Annotations are declared semantically
  (kind, semantic, datum, side, row). All sheet coordinates belong to
  `SheetPlan.solve()`; there is nothing to hand-nudge.
- **Audit before render.** `plan.report()` is reviewed and every warning
  either fixed or explicitly accepted with a reason before `render()`.
- **Two artifacts, one truth.** The PNG is rendered from the DXF. Visual
  acceptance means reading the PNG; "no rule conflicts" alone is not
  acceptance.

## Stage 0 — Preconditions ⛔

All must hold; otherwise stop and finish modeling/verification first:

1. Geometry validated by its owning workflow (e.g.
   `workflows/single-part-modeling.md` or `workflows/assembly-product-build.md`)
   and, where applicable, captured.
2. The parameter set that the drawing must express is known — every model
   parameter will need a carrier (dimension `covers` or the notes/parameter
   table, rule R5).
3. Drawing-level choices are decided or askable: sheet scale, view set,
   datum letters, which parameters are manufacturing-critical.

Ask-or-Record: batch any blocking ambiguity (scale, view count, datum
choice) in one round with conservative defaults; record the rest as
assumptions with their basis.

## Stage 1 — Declare views

For each view, declare a `ViewDecl` in view-local model coordinates:

- `n` = viewing direction, `xd` = in-projection-plane "screen right" — pick
  them so the first-angle projection of the chosen views satisfies
  长对正 / 高平齐 naturally (front–top, front–left pairs).
- Anchor the front view via `SheetDecl.front`/`anchor`; align every other
  view with `align={"to": <view>, "side": "below"|"right", "gap": <mm>}` —
  never by computed offsets.
- Add `CenterDecl` (line or arc) for axes and symmetry so the solver can
  treat them as geometry during collision checks.

## Stage 2 — Declare datums and dimensions

- Declare the datum system first (`DatumDecl`: A as primary, B/C auxiliary).
- Declare `DimDecl`s with the two-axis classification:
  `kind` (`size` = shape, `position` = location, must reference a `datum`,
  `overall`) × `semantic` (`linear` with `p1`/`p2`, `diameter`/`radius` with
  `center`/`radius`/`at` azimuth).
- Give every dimension `covers` naming the model parameters it carries;
  uncaptured parameters must be destined for notes or the parameter table.
- Prefer declaring intent (`side`, `row`) over fighting for space; the
  R4 row slots and the `out` ladder exist so you do not have to.

## Stage 3 — Solve and audit

```python
plan = SheetPlan(decl).solve()
print(plan.report())
```

Review the report line by line:

- Every element shows `ok` or a recorded least-adjustment deferral; R1
  warnings are layout problems — fix declarations (Stage 1/2) and re-solve.
- R5 coverage table: no `MISS`. A parameter becomes either a dimension
  (`covers`) or an explicit note/parameter-table row.
- `plan.accepted` entries need a stated reason; do not accept silently.

## Stage 4 — Render and visual review

`plan.render(sheet.dxf, sheet.png)` writes both artifacts. Then read the PNG:

1. Views aligned as declared; hidden lines (虚线) and center lines present.
2. Arrows touch their geometry; texts sit clear of lines; datum boxes legible.
3. The dimension arrangement communicates the design intent (a solver-clean
   sheet can still mislead — e.g. dimensioning a derived length instead of
   the functional one).

If the PNG disagrees with the report, trust the PNG and fix declarations.
Never post-edit the DXF by hand — regenerated sheets must stay reproducible
from the declaration alone.

## Acceptance

- `report()`: R1–R7 all ok, or accepted with recorded reasons.
- R5: every model parameter has a carrier; no `MISS`.
- PNG reviewed and correct; DXF re-opens (e.g. via `ezdxf`) with the expected
  entity count; both artifacts regenerate deterministically from the same
  `SheetDecl`.

## Failure modes

- Entering with unvalidated geometry: every downstream conflict then looks
  like a drawing bug but is a model bug.
- Over-constraining placement (fighting `side`/`row`) instead of accepting
  the solver's least-adjustment deferrals.
- Declaring dimensions for derived/intermediate values while the functional
  parameters stay uncovered (R5 passes formally, drawing misleads).
- Hitting engine boundaries (no sections/hatching; horizontal/vertical
  linear dims only; radius labels same-side outward): restructure the view
  set or record the limitation; do not simulate missing features with
  leader-note spam.
