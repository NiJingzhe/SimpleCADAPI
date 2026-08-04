# compare_entities_rdescriptor

## API Definition

```python
def compare_entities_rdescriptor(target: ModelInput, target_entity_id: str, current: ModelInput, current_entity_id: str) -> dict[str, Any]
```

*Source: inspect/brep/diagnostics.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_entities_rdescriptor(...)`; unavailable inside GraphSession/@model

## Description

Compare entity geometry, scalar parameters, distance, and adjacency.
