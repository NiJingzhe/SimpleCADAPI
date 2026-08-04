# inspect_step_entity_rdescriptor

## API Definition

```python
def inspect_step_entity_rdescriptor(path: str | Path, entity_id: str, *, include_curve_definition: bool = False, include_surface_definition: bool = False, max_surface_control_points: int = 256) -> dict[str, Any]
```

*Source: inspect/brep/model.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.inspect_step_entity_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Return geometry, measurements, bounds, and adjacency for one entity id.
