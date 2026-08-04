# inspect_difference_regions_rdescriptor

## API Definition

```python
def inspect_difference_regions_rdescriptor(target: ModelInput, current: ModelInput, *, distance_threshold: float = 0.1, linear_deflection: float = 0.5, max_samples: int = 600, cluster_radius: float | None = None, merge_radius: float | None = None, boolean_tolerance: float | None = None, include_boundary: bool = False, boundary_result: Mapping[str, Any] | None = None, material_result: Mapping[str, Any] | None = None) -> dict[str, Any]
```

*Source: inspect/brep/diagnostics.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.inspect_difference_regions_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Aggregate material components and optional precomputed boundary anomalies.
