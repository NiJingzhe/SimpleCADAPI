# compare_sections_rdescriptor

## API Definition

```python
def compare_sections_rdescriptor(target: ModelInput, current: ModelInput, plane_origin: Sequence[float], plane_normal: Sequence[float], *, tolerance: float = 1e-07, samples_per_edge: int = 32) -> dict[str, Any]
```

*Source: inspect/brep/diagnostics.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_sections_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Compare target and current contour geometry on one physical plane.
