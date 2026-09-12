# DrawingCalibration

## Class Definition

```python
class DrawingCalibration(pair_count: int, scale_mm_per_pt: float, scales_per_pair: list[float], max_relative_deviation: float, relative_tolerance: float, min_pairs: int, accepted: bool)
```

*Source: inspect/drawing/calibrate.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.DrawingCalibration(...)`; unavailable inside GraphSession

## Description

Consensus mm-per-pt scale fitted from independent known dimensions.

``accepted`` requires at least ``min_pairs`` pairs and all per-pair
scales agreeing within ``relative_tolerance``. A calibration that failed
must never be used to produce derived numbers: fix the anchor selection
or the measurement instead.
