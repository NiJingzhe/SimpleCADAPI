# export_model_json

## API Definition

```python
def export_model_json(session: 'GraphSession', indent: int = 2, *, result_node_ids: Optional[Sequence[str]] = None) -> str
```

*Source: serializer.py*

## Import Surface

- top-level: `from simplecadapi import export_model_json`

## Description

Export the canonical 2.0 model seed JSON.

Current Phase 1 scope uses the active session as the container of:
- operation graph
- expression graph
- capabilities/schema metadata
