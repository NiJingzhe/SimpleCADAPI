# inspect_point_rdescriptor

## API Definition

```python
def inspect_point_rdescriptor(model_or_path: BRepModel | TopoDS_Shape | str | Path, point: Sequence[float], entity_kinds: Sequence[str] = ('face', 'edge', 'vertex'), limit: int = 20) -> dict[str, Any]
```

*Source: inspect/brep/queries.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.inspect_point_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Return exact point-to-entity distances, ordered by distance then stable id.
