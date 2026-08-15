# validate_step_roundtrip_rdescriptor

## API Definition

```python
def validate_step_roundtrip_rdescriptor(model_or_shape: ModelInput, output_path: str | Path, *, relative_property_tolerance: float = 1e-07, position_tolerance: float = 1e-06, protected_input_paths: tuple[str | Path, ...] = (), compact: bool = True) -> dict[str, Any]
```

*Source: inspect/brep/persistence.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.validate_step_roundtrip_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Atomically write and reload STEP, publishing only a verified result.

Relative tolerance bounds volume and surface-area drift. Position tolerance,
in model length units, bounds centroid distance and bounding-box coordinate
drift. The returned descriptor records each measured delta.
