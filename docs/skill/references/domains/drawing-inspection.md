# Task Domain: Engineering-Drawing Inspection (Vector PDF)

Extract traceable evidence from vector-PDF engineering drawings with the
`simplecadapi.inspect.drawing` namespace: health probing, text-layer
inventory, rendered viewports, and calibrated vector measurement. Everything
this domain produces feeds the parse report consumed by
`workflows/drawing-reconstruction.md`.

## Use when

- The input is a vector-PDF engineering drawing (AutoCAD/CATIA/NX print
  output) and the task needs its content as structured, tiered evidence.
- A generated model must be read back through the same evidence pipeline for
  the drawing-roundtrip comparison (report B).
- Section views must be verified visually: cut the rebuilt model at the
  drawing's section planes, render the cut faces with measured dimension
  annotations, and pair them with the original viewports for isolated
  review (`measure_model_section_rdimensions`,
  `render_model_section_rpath`).
- Region viewports (overview and zoomed crops) are needed for annotation
  reading or for an isolated visual reviewer.

## Do not use

- Raster-only images, DXF, or DWG inputs: no supported route exists yet.
  Name the missing capability and stop; do not improvise an OCR route.
- Building or editing geometry: these functions are diagnostic, not modeling
  operations, and are rejected inside `GraphSession`.
- STEP/BREP files: that is `domains/step-inspection.md`.

## Coordinate contract

PDF coordinates use `page_display` in **pt**, rendered images use **px**,
and model sections use `section_local` in **mm**. These are distinct spaces.
Text boxes and page rendering passed the audited scenarios; this is not a
universal guarantee for arbitrary PDFs. The older vector implementation
ignored page rotation. Result version 2.0 transforms line endpoints, Bezier
control points and all rectangle/quad corners, then filters their transformed
bounds. Every input still needs the coordinate preflight below. Unchecked
coordinates cannot support a verified DIM.

With the fixed SDK, a direction-normalized copy is not a routine prerequisite.
Use the original file after its per-page coordinate preflight passes; reserve
normalization for legacy versions or a demonstrated abnormal page.

Page-to-pixel conversion must include the effective crop and integer pixmap
origin; use the sidecar forward/inverse matrices, never simply subtract the
requested crop origin. Page lengths become model lengths only through a
separate accepted calibration for each view.

### Coordinate preflight (before parsing)

Archive the original file and record SHA-256, zero-based page index, page
rotation, MediaBox, CropBox, coordinate space, units, SDK/result and PDF-engine
versions. For **each page**, check text boxes and directions, line/curve/corner
landmarks against the rendered positions. Save crops, independently observed
pixel landmarks, transform checks, reviewer and verdict in
`coordinate_preflight.json`; metadata or an algebraic roundtrip alone is not
visual alignment proof. `inspect_drawing_coordinates_rreport` evaluates these
observations and keeps absent text/vector checks pending.

For legacy rotation failures, a verified direction-normalized working copy
is allowed. Preserve the original, both hashes, page mapping and exact forward
and inverse transforms in the normalization script's record. Verify the copy
before use. All downstream text, vectors, crops and
calibration must use that same copy and source ID. Never mix coordinates from
original and normalized files. A failed page blocks only its dependent DIMs.

## API groups

Read the exact page under `references/docs/api/` for every API used:

- Inventory: `inspect_drawing_rsummary` — per-page sizes/rotation, text
  counts, path/primitive counts with kind and color census, metadata, fonts,
  and the `route` verdict (`vector`/`raster`/`mixed`/`text_only`/`empty`).
  Only a `vector` verdict supports measured claims.
- Text layer: `extract_drawing_text_rwords` — every text object with
  display-space boxes, original objects and text directions plus proximity
  clusters that propose value/tolerance combinations. Unordered: an inventory, not a
  reading.
- Viewports: `render_drawing_view_rpath` — full-page overviews or region
  crops (`rect`, or `anchor` = a word/cluster dict framed with margin so
  leader lines stay attached). Each PNG gets a JSON sidecar recording the
  source rect and dpi.
- Vector layer: `extract_drawing_primitives_rstrokes` — normalized
  primitives (line/bezier/quad/rect) with colors and widths; filter per view
  by `rect`, `color`, `fill`, `kinds`. Region selection is inclusive bounding
  box overlap, not exact curve clipping. Vectors become measurement evidence
  only after coordinate and feature-association checks; pixels are not metrology.
- Calibration and measurement: `calibrate_drawing_scale_rcalibration`
  (consensus mm/pt from ≥3 independent known dimensions, residuals, accepted
  verdict) and `measure_drawing_rmeasurements` (point distances, stroke
  lengths, mm conversion through an accepted calibration).

## Model-section evidence group

Cut the rebuilt model where the drawing cuts it; these functions take a live
shape (pass ``solid.wrapped``) or a STEP path and an explicit plane, and stay
factual — plane semantics belong to the caller:

- `measure_model_section_rdimensions` — distinguish analytic circle geometry,
  fitted-circle candidates, continuous geometry extrema/distances and sampled
  approximations by each record's method and accuracy fields. A fitted circle's
  residual is not a dimensional error bound. Section intersection tolerance is
  not total measurement uncertainty. Unknown error bounds stay unknown.
  Circle diagnostics include conditioning, angular coverage/max gap and both
  RMS/max residual. Local arcs, open/gapped contours and nearly collinear
  samples stay unverified; do not modify CAD dimensions from unreliable fits.
- `render_model_section_rpath` — annotated section render (45° hatch on
  material only, dimension leaders with `dim_id` + measured value + sheet
  value, mm scale bar). Fixed output: the section PNG and sidecar. The
  renderer displays caller data, including wrong numbers; rendering success
  does not prove measurement correctness. Formal evidence must use the bound
  annotation builder and independent validator. The caller owns the comparison: put the render next to the drawing's own
  viewport crop (same evidence directory) and judge — no composite is
  generated for you.

### Explicit section strategy and integrity evidence

Result version **2.2** adds `section_strategy="auto"|"material"|"edges"`.
Auto uses material-face intersection for solids even if edge contours would
already be closed, and edge intersection for non-solid diagnostic inputs.
Material mode retains the actual edges and topological outer/inner wire roles
from the same intersection. Edges mode remains available; with formal checks
it also obtains an independent material-face reference. Environment variable
`SIMPLECADAPI_MATERIAL_SECTION` no longer selects the workflow strategy.
Archive both the requested strategy and the actual `contour_method`.

Each formal DIM ledger row must reference the same independently reviewed
`section_checks` contract as its measurement. For a tube cut at z=10, an example
contract is:

```json
{
  "expected_origin": [0, 0, 10],
  "expected_normal": [0, 0, 1],
  "expected_x_direction": [0, -1, 0],
  "expected_y_direction": [1, 0, 0],
  "expected_solid_count": 1,
  "expected_face_count": 1,
  "expected_hole_count": 1,
  "material_points": [{"id": "wall", "point": [9, 0]}],
  "void_points": [{"id": "bore", "point": [0, 0]}],
  "point_tolerance_mm": 0.0000001,
  "tolerance_basis": "Point-classification precision for this fixture",
  "evidence": "Drawing view and independent feature-association review"
}
```

The example's points assume an outer radius of 10 and inner radius of 8;
choose actual points from the intended drawing geometry. Expected counts and
directions come from the drawing/confirmed requirements, never from copying the
current result. Points are section-local mm. Every material face needs an
interior material point; every hole needs an interior void point. Boundary or
indeterminate classifications stay pending. Empty void lists are allowed only
when no topological hole needs coverage; include points in any additional
drawing-defined open cavity or gap. The coordinate-frame direction comparison
uses the recorded numerical threshold 1e-10; point tolerance is not a dimensional
error bound.

`section_validation` separately reports source validity/closure/solid count,
section closure, valid material faces and inner/outer rings, and each point's
classification against the original solid, material faces, and displayed
polygons. Formal rendering checks its own actual sampling density. Open or
incomplete sections may render as `diagnostic_only`, but cannot become formal
evidence. Missing section checks are not auto-filled from measured geometry.

On failure, inspect the section definition, intersection and display first.
`section_definition`, `section_intersection` and `section_display` failures
do not justify changing the model. Only independent solid evidence, confirmed
against the drawing, can establish a model-geometry error. Mass, center of mass,
inertia and high-precision volume matching remain outside drawing-reconstruction
acceptance unless the user separately requests them.

## Section-plane parsing rules (deterministic, never asked)

Resolve a drawing's section views to cut planes by these conventions; the
resolution is recorded in the report's view list as 〔归属〕:

- **R1 Projection**: the section plane is perpendicular to the view the
  cutting symbol is drawn on; the symbol's line position, converted through
  the calibrated scale, is the plane position.
- **R2 Direction**: the symbol arrows give the viewing direction; a full
  section without arrows takes the principal viewing direction.
- **R3 Full-section default**: an unlettered full section (main view) cuts
  through the part's axis / symmetry plane.
- **R4 Position anchoring**: resolve the cut position from text-layer
  dimension anchors near the symbol (e.g. "C-C at mid spiral-groove zone"),
  never by eyeballing the render.
- **R5 Exclusions**: detail/enlarged views are not sections — they stay in
  the viewport-comparison channel.
- **R6 Degradation**: an ambiguous or incomplete cutting symbol marks the
  view `unreviewable` in the gap list; never guess a plane.
- **R7 Blame order**: on a section mismatch, re-check the plane resolution
  (R1–R4) before suspecting the model.

## Parsing SOP

Run in order; each step has a deliverable:

0. **Coordinate preflight** — archive and validate each page as above. Deliverable:
   source/transform records and separate text/vector/render verdicts.
1. **File checkup** — `inspect_drawing_rsummary`. Deliverable: the health
   table and the route verdict. Non-vector routes stop here.
2. **Text-layer inventory** — `extract_drawing_text_rwords`. Deliverable:
   the complete annotation inventory with coordinates. Existence only:
   reading order is not visual order.
3. **Overview pass** — `render_drawing_view_rpath` full page at ~150 dpi.
   Deliverable: the view map (view names, section letters A/B/C/D, detail
   view indices, tables, title block).
4. **Region reading** — per view, `render_drawing_view_rpath` crops at high
   dpi (anchors from step 2 give the framing). Deliverable: every annotation
   read verbatim, including superscript/subscript tolerance stacks. The
   rendered view decides attachment; the text layer decides completeness.
5. **Calibration and measurement** — per view independently: pick ≥3
   geometrically independent known dimensions, calibrate, and require
   `accepted`; only then measure unknowns and cross-check them against
   annotated values. Detail views carry their own scales (1:1, 2:1, 4:1).
   Deliverable: measurement records with provenance.
6. **Dimension association verification** — independently connect original text
   objects to dimension lines, extension lines, arrows/leaders, measured features,
   geometry and datums. Record `verified`, `ambiguous` or `unresolved`, with
   evidence references and reviewer. Proximity only proposes combinations; it
   cannot confirm tolerance stacks or feature attachment. Signed angles follow
   the datum, geometric direction and declared coordinate convention, never the
   text's position above/below a horizontal line. Ambiguous/unresolved DIMs cannot
   be verified; unaffected work may continue.
7. **Semantic assembly** — standard symbols → normative semantics (cite the
   standard); verified annotations → feature attachment. Produce the tiered entries
   below. Deliverable: the tiered data tables.
8. **Report and self-check** — write the parse report skeleton, run its
   checklist, archive the process files. Deliverable: the parse report.

## Information tiers (binding for every statement)

Every statement in a parse report falls in exactly one tier; a fourth
category is forbidden.

| Tier | Marker | Source tag | Meaning | Rule |
| --- | --- | --- | --- | --- |
| 1 | 〔图面〕 | `drawing_annotation` | Text/number/symbol/table literally on the sheet | Cite the view and annotation; tables quoted verbatim |
| 2 | 〔归属〕 | `geometric_interpretation` | Attaching an annotation to a feature ("this dimension is that bore") | Justify via leader/extension/section evidence; must enter the review checklist |
| 3 | 〔推算〕 | `measured_derivation` | Numbers derived from vector measurement + calibration | State calibration and verification; kept separate from annotated values, never merged |

Forbidden: part function, purpose, industry-context inference ("typically
used as…", "presumably a …"). Low confidence is a reason not to write, not a
license to write. Function words printed on the sheet are quoted as
〔图面〕 without expansion. Standard definitions may be cited as external
facts (with the standard number), but mapping a symbol to a concrete object
the sheet does not label stays at "not annotated on the sheet". Derived
values that agree with an annotation are reported as "cross-validation
passed", never promoted to annotated status.

## Parse report skeleton

Ten sections, copied per case (the tier markers and red lines apply
throughout):

```markdown
# {file} CAD Engineering-Drawing Parse Report
> Method: {text layer + N dpi renders + vector measurement}  Date: {date}
## 1. File facts            (metadata, fonts, primitives, title-block state)
## 2. View list             (view/scale 〔图面〕; "what it shows" column is 〔归属〕)
## 3. Dimension ledger      (per view; each entry: DIM-id, value, tolerances,
                            attaching view, tier mark, provenance viewport)
## 4. Tolerances, GD&T, datums
## 5. Surface quality
## 6. Technical requirements / tables, verbatim
## 7. Vector measurement records (calibration, verification points, derived values)
## 8. Review checklist      (every 〔归属〕 conclusion collected here)
## 9. Not contained in this file (referenced schedules, missing sheets, blank fields)
## 10. Appendix: process files
```

The dimension ledger (section 3) is the join key for the drawing-roundtrip
comparison: give every dimension a stable `DIM-xxx` id, because report B is
diffed against report A parameter by parameter. Section 2's view list doubles
as the acceptance render list for the roundtrip.

Each DIM row additionally records: source hash/page/coordinate-preflight ID;
raw word IDs and objects, direction, verbatim value/deviations and units;
combination candidate IDs; dimension/extension/arrow/leader stroke IDs and
evidence crops; feature ID, target geometry IDs, datum and view; association
status/reason/reviewer; tolerance bounds and their cited basis (or `unspecified`);
measurement contract/result ID/model hash/section ID; independent original
interpretation, model measurement and output-expression verdicts. Coverage
counts `value_verified`, `association_verified`, and `layout_reviewed`
separately, with missing DIM IDs for each column.

### Executable evidence checks

Read the exact API pages for `inspect_drawing_coordinates_rreport`,
`assess_dimension_rverdict`, `build_section_annotation_rrecord`,
`validate_section_annotations_rreport`, and
`summarize_dimension_coverage_rreport`. The latter requires the complete expected
DIM list; omitted rows count as missing in every coverage column.

Result version **2.1** requires an independent `measurement_contract` in each
ledger row. For example, a section's width is
`{"kind":"extent_width","definition":"axis_aligned_extent","direction":[1,0],
"point":null,"units":"mm","coordinate_space":"section_local"}`.
Height uses `extent_height` and `[0,1]`. Diameter uses `circle_diameter`,
minimum gap uses `minimum_boundary_gap`, both with null direction/point.
Directional material thickness uses `material_length_on_line`, a normalized
local direction and the specified local point. Geometry IDs bind the selected
contour; this separate contract binds what is measured on it. Missing contracts
cannot be inferred from whichever measurement happens to fall inside tolerance.

The repository script `tools/verify_drawing_evidence.py --model part.step
--evidence evidence.json --out verification.json` independently remeasures and
reports all three gates. Its input contains `plane`, the complete `ledger`,
bound `annotations`, and `output_reviews` keyed by DIM ID. An output review
contains `layout_status: reviewed`, `association_status: verified` and independent
`evidence` references, plus the `dim_id`, `measurement_id`, `model_hash` and
`section_id` captured **when the image was reviewed**. Its `render_artifact`
contains absolute `image_path`, `sidecar_path`, and the reviewed
`image_sha256`, `sidecar_sha256`. The renderer records the image hash and each
annotation's content-derived ID in the sidecar. Validate both file hashes,
annotation content (including anchors and precision) and measurement identity.
Never replace old review IDs or hashes with current values during verification.
Old or missing identities require a new review of the actual current artifact.
Missing visual review remains pending even when numeric checks pass.

Formal annotations also check the actual formatted value: the display step
must be no wider than the tolerance band, rounding error no larger than half
its width, and the displayed number itself inside the band. Zero-width bands
require exact representation. For 10.4 mm in [10.39,10.41], zero decimals are
rejected; one decimal also lacks the required resolution. Geometric conformance
continues to use the unrounded value and its uncertainty interval.

An external total-error assessment must be tied to the exact `measurement_id`
and include `bound_mm`, `basis`, and `evidence`. These fields record a separate
metrology assessment; the SDK cannot establish its truth just by reading them.
Do not turn a fitted-circle residual or kernel edge tolerance into this bound.

## Discipline notes

- Text extraction order ≠ visual order; tolerance stacks and fraction texts
  split apart. The text layer is the "what exists" list; the zoomed viewport
  is the reading.
- Calibrate per view, ≥3 independent anchors, `accepted` or no derived
  numbers. Distinguish contour lines / dimension lines / extension lines /
  hatch lines (by color and length) before measuring.
- "Vertical outline length ≈ diameter" holds only for revolved-body contour
  lines, never for extension lines.
- Sheet scale and title-block scale may disagree (fit-to-page printing);
  the title-block "1:1" often means model units.
- Colors carry per-drawing conventions (cyan hatch = machined face, red =
  hole axes — discovered per sheet, not assumed). The census reports facts;
  meaning assignment is 〔归属〕.
- Check "sheet X of Y": multi-sheet sets may arrive partially.
- Copy the source file to the working directory first; temp transfer
  directories expire.
