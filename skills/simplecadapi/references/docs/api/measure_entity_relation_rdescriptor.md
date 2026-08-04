# measure_entity_relation_rdescriptor

## API Definition

```python
def measure_entity_relation_rdescriptor(model_or_path: BRepModel | TopoDS_Shape | str | Path, first_entity_id: str, second_entity_id: str, tolerance: float = 1e-07, angular_tolerance_degrees: float = 0.0001, second_model_or_path: BRepModel | TopoDS_Shape | str | Path | None = None) -> dict[str, Any]
```

*Source: inspect/brep/queries.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.measure_entity_relation_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Measure exact distance and conservatively report supported analytic relations.
