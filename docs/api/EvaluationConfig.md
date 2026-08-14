# EvaluationConfig

## Class Definition

```python
class EvaluationConfig(target_kind: str = 'solid', stage_timeout_seconds: float = 120.0, material_timeout_seconds: float = 300.0, global_max_bbox_delta: float = 0.1, global_max_centroid_distance: float = 0.1, global_max_relative_volume_error: float = 0.01, global_max_relative_area_error: float = 0.01, strict_material_tolerance: float = 1e-06, boundary_linear_deflection: float = 0.2, boundary_max_samples: int = 200, boundary_max_hausdorff: float = 0.1, boundary_max_p95: float = 0.1, sections: tuple[SectionEvaluationConfig, ...] = (), strict_geometric_tolerance: float = 1e-07)
```

*Source: inverse_engineer/brep/evaluation.py*

## Import Surface

- reverse-engineering evaluator: `from simplecadapi.inverse_engineer.brep import EvaluationConfig`

## Description

Closed configuration contract for trusted reconstruction evaluation.
