# measure_drawing_rmeasurements

## API Definition

```python
def measure_drawing_rmeasurements(selections: Sequence[Mapping[str, Any]], *, calibration: Mapping[str, Any] | None = None) -> DrawingMeasurements
```

*Source: inspect/drawing/calibrate.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.measure_drawing_rmeasurements(...)`; unavailable inside GraphSession

## Description

Measure display-space geometry and optionally convert to millimetres.

Selections are self-contained: ``{"kind": "distance", "a": [x, y],
"b": [x, y], "label": "..."}`` measures the Euclidean distance between
two points; ``{"kind": "stroke_length", "points": [[x, y], ...],
"label": "...", "stroke_kind": "line"|"bezier"|"polyline"}`` measures the
polyline through ``points`` (pass the ``points`` of one stroke from
``extract_drawing_primitives_rstrokes``; ``bezier`` control polygons are
sampled, not chorded). ``calibration`` is the dict returned by
:func:`calibrate_drawing_scale_rcalibration`; without it ``length_mm``
stays ``null``. Only pass a calibration whose ``accepted`` is true.
