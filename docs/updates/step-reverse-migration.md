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
