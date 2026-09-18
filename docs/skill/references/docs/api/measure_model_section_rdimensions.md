# measure_model_section_rdimensions

## API Definition

```python
def measure_model_section_rdimensions(model: Any, plane: Mapping[str, Sequence[float]], *, tolerance: float = 1e-07, samples_per_edge: int = 64, circle_tolerance: float = 0.02, directional_thickness: Sequence[Mapping[str, Any]] | None = None, section_strategy: str = 'auto', section_checks: Mapping[str, Any] | None = None, circle_min_coverage_degrees: float = 270.0) -> DrawingSectionDimensions
```

*Source: inspect/drawing/section.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.measure_model_section_rdimensions(...)`; unavailable inside GraphSession

## Description

Cut the model at one plane and measure candidate dimensions.

``plane`` is ``{"origin": [x, y, z], "normal": [nx, ny, nz]}`` in model
coordinates; ``model`` is a live shape or a STEP path. Candidates come
from actual section edges: analytic circles precede fitted-circle
candidates, extents use continuous BREP bounds and nested contour gaps
use continuous BREP distance. Pair nesting remains a sampled association
candidate in edges mode; material mode uses topological outer/inner wires.
``directional_thickness`` entries require ``id``, a local 2D
``point`` and nonzero ``direction``; each connected material interval on
that line is reported separately. A radial query uses a center as point
and the specified radial direction; select the intended interval explicitly.
Records contain method, contour/edge IDs, configuration, accuracy class,
residuals, source/model/section hashes and content-derived measurement IDs.
``measurement_contract`` identifies kind, definition, direction, line point,
units and coordinate space separately from target_geometry. The ledger must
independently specify that contract; width and height on one contour differ.
Error bounds are unknown unless independently established: neither kernel
tolerance nor circle-fit residual proves total dimensional accuracy.

``section_strategy`` selects auto (material faces for solids, edges for
non-solid diagnostics), material (solid/plane face intersection), or edges
(section edges). It replaces the environment-variable fallback; even closed
contours may use material mode. The actual contour_method is recorded.
``section_checks`` supplies independently resolved expected_origin/normal/
x_direction/y_direction, expected_solid_count/face_count/hole_count, lists of
material_points and void_points ({id, point:[u,v]}), point_tolerance_mm,
tolerance_basis and evidence. Every face and hole needs representative point
coverage. Edges mode also computes a material-face reference for these checks.
The same contract must appear in each corresponding ledger row. Missing or
uncertain checks keep formal evidence pending. No mass, centroid, inertia or
high-precision volume-equivalence gates are added.
``circle_min_coverage_degrees`` defaults to 270 for sampled fit candidates.
Diagnostics include coverage, maximum angular gap, conditioning and RMS/max
residual; open contours and degenerate samples never establish a full circle.
Analytic full-circle geometry has its own exact angular-coverage check.
