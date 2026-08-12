# STEP Reverse Implementation Migration

This document records the selected implementation changes migrated from the
`STEP-reverse` branch. Later migration commits append numbered entries to this
same document.

## 1. Analytic Face Fitting, Section Tracking, and Comparison Rendering

Added three inspection APIs under `simplecadapi.inspect.brep`:

- `fit_face_analytic_rdescriptor(...)` samples an indexed BREP face and fits
  plane, sphere, cylinder, and cone carriers. It reports candidate parameters
  and residual statistics as reconstruction evidence without asserting feature
  history.
- `track_section_contours_rdescriptor(...)` matches closed contours across
  ordered sections and reports continuation, birth, death, split, and merge
  events. Its summary indicates when topology changes make a single global loft
  unsafe.
- `render_step_comparison_rpath(...)` renders original and reconstructed STEP
  models side by side with identical views, camera bounds, and scale so visual
  size and placement differences are not hidden by per-model camera fitting.

Added focused regression tests for cylindrical carrier fitting, contour birth
detection, and shared-view STEP comparison image generation. No bounded STEP
comparison, topology fingerprint, or public-export-only changes were included.

Updated the bundled `simplecadapi` Skill with selection rules, reverse-
engineering usage guidance, API index entries, and exact reference pages for
the three inspection APIs.

## 2. Grouped STEP/BREP Comparison Diagnostics

Extended `BRepComparison` with structured diagnostic facts for STEP validity,
bounding boxes, material volume and bidirectional Boolean difference,
topology counts, Face-Edge topology, and surface/curve carrier types. The
strict geometric and topology hard gate remains unchanged.

Added `to_error_summary()` and `write_error_summary_json(...)` to report every
failed comparison check instead of stopping at one reason. Each error includes
its code, expected and actual values, plausible causes, affected modeling
stages, and severity. Related errors are grouped by a plausible common root
cause, with an iteration policy that permits coordinated fixes within one
group before rerunning Direct modeling, strict replay, STEP export, and the
complete comparison.

Added regression coverage for successful comparisons, simultaneous material
and placement failures, common-root-cause grouping, iteration-policy output,
and JSON artifact writing. Updated the bundled `simplecadapi` Skill API pages
and reverse-engineering guidance for the new comparison diagnostics and error
summary workflow.
