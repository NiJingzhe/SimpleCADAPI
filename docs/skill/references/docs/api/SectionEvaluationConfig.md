# SectionEvaluationConfig

## Class Definition

```python
class SectionEvaluationConfig(section_id: str, origin: tuple[float, float, float], normal: tuple[float, float, float], tolerance: float = 1e-07, samples_per_edge: int = 16, require_nonempty: bool = True, max_hausdorff: float = 0.1, max_relative_area_error: float = 0.01)
```

*Source: inverse_engineer/brep/evaluation.py*

## Import Surface

- reverse-engineering evaluator: `from simplecadapi.inverse_engineer.brep import SectionEvaluationConfig`

## Description

One bounded diagnostic section probe used by reconstruction evaluation.

Coordinates and tolerance are millimetres, and ``samples_per_edge`` is an
integer measurement control. Section IDs must be unique within an
``EvaluationConfig``. Section results are diagnostics, not acceptance gates.
``require_nonempty``, ``max_hausdorff``, and ``max_relative_area_error`` are
deprecated compatibility inputs and do not affect stage status.
