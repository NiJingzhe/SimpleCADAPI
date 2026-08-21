# compare_material_region_rdescriptor

## API Definition

```python
def compare_material_region_rdescriptor(target: ModelInput, current: ModelInput, *, region_min: Sequence[float], region_max: Sequence[float], boolean_tolerance: float | None = None, output_directory: str | Path | None = None, max_components: int = 100) -> dict[str, Any]
```

*Source: inspect/brep/diagnostics.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_material_region_rdescriptor(...)`; unavailable inside GraphSession

## Description

Compute directional material differences inside one axis-aligned ROI.
