# evaluate_reconstruction_rdescriptor

## API Definition

```python
def evaluate_reconstruction_rdescriptor(target: ModelInput, current: ModelInput, *, replay_succeeded: bool, boundary_tolerance: float = 0.1, bounding_box_tolerance: float = 0.1, relative_volume_tolerance: float = 0.001, relative_area_tolerance: float = 0.001, relative_material_tolerance: float = 0.001, linear_deflection: float = 0.5, max_samples: int = 600, boolean_tolerance: float | None = None, strict_geometric_tolerance: float = 1e-06, strict_material_tolerance: float = 1e-06, require_strict_brep: bool = False) -> dict[str, Any]
```

*Source: inspect/brep/diagnostics.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.evaluate_reconstruction_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Apply replay, validity, material, boundary, and optional strict gates.
