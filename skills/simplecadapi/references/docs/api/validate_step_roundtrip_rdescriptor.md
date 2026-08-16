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

Relative tolerance bounds candidate-before/after volume and surface-area
drift. Position tolerance, in model length units, bounds candidate-before/
after centroid distance and both material and root bounding-box coordinate
drift. These are STEP serialization integrity checks, not candidate-to-target
similarity metrics. The returned descriptor records each measured delta.
Topology acceptance compares defect counts and shell facts, preserving
existing open topology while rejecting newly introduced defects and shell
closure, orientation, or closed-manifold regressions.
