# select_region_entities_rdescriptor

## API Definition

```python
def select_region_entities_rdescriptor(model_or_path: BRepModel | TopoDS_Shape | str | Path, entity_ids: Sequence[str] | None = None, center: Sequence[float] | None = None, radius: float | None = None, depth: int = 0) -> dict[str, Any]
```

*Source: inspect/brep/queries.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.select_region_entities_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Expand stable ids through topology and optionally filter them by bounds distance.
