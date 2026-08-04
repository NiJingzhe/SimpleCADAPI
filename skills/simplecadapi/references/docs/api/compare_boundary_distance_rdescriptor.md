# compare_boundary_distance_rdescriptor

## API Definition

```python
def compare_boundary_distance_rdescriptor(target: ModelInput, current: ModelInput, *, linear_deflection: float = 0.5, max_samples: int = 200, target_face_ids: Sequence[str] | None = None, current_face_ids: Sequence[str] | None = None, include_records: bool = False) -> dict[str, Any]
```

*Source: inspect/brep/diagnostics.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_boundary_distance_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Compute bidirectional sampled-boundary to exact-boundary distances.
