# inspect_topology_neighborhood_rdescriptor

## API Definition

```python
def inspect_topology_neighborhood_rdescriptor(model_or_path: BRepModel | TopoDS_Shape | str | Path, entity_id: str, depth: int = 1, max_entities: int = 100) -> dict[str, Any]
```

*Source: inspect/brep/queries.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.inspect_topology_neighborhood_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Return a deterministic, bounded breadth-first topology neighborhood.
