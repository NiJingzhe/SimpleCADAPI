# inspect_nearby_entities_rdescriptor

## API Definition

```python
def inspect_nearby_entities_rdescriptor(model: ModelInput, *, location: Sequence[float] | None = None, region: Mapping[str, Any] | str | None = None, radius: float = 1.0, entity_types: Sequence[str] = ('face', 'edge', 'vertex'), max_results: int = 30) -> dict[str, Any]
```

*Source: inspect/brep/diagnostics.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.inspect_nearby_entities_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Find stable entities whose exact geometry lies near a point or region.
