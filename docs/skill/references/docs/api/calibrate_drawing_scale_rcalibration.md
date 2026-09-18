# calibrate_drawing_scale_rcalibration

## API Definition

```python
def calibrate_drawing_scale_rcalibration(pairs: Sequence[Mapping[str, Any]], *, relative_tolerance: float = 0.01, min_pairs: int = 3) -> DrawingCalibration
```

*Source: inspect/drawing/calibrate.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.calibrate_drawing_scale_rcalibration(...)`; unavailable inside GraphSession

## Description

Fit one mm-per-pt scale from independent known dimensions and verify it.

Each pair is either ``{"a": [x, y], "b": [x, y], "dim_mm": v}`` (two
display-space points of a feature whose real dimension is known) or
``{"length_pt": v, "dim_mm": v}``. The consensus scale is the mean of the
per-pair scales; ``accepted`` is true only with at least ``min_pairs``
pairs whose scales agree within ``relative_tolerance``. Calibrate per
view: detail views are drawn at their own scales (1:1, 2:1, 4:1) and one
global factor is wrong for them by construction. Use dimensions that are
geometrically independent; two deviations of the same chain are not two
anchors.
