# compare_material_rdescriptor

## API Definition

```python
def compare_material_rdescriptor(target: ModelInput, current: ModelInput, *, boolean_tolerance: float | None = None, output_directory: str | Path | None = None, include_components: bool = True) -> dict[str, Any]
```

*Source: inspect/brep/diagnostics.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_material_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Compute missing/excess volumes using directional cuts by default.
