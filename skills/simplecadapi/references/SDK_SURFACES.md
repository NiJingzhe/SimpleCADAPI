# SDK Surfaces

## Public API groups

- Primitive and sketch construction functions
- Transform, feature, boolean, and export functions
- Assembly and constraint entry points
- Graph/model serialization and replay entry points
- Expression and semantic reference data types

## Recommended reading order

1. `references/docs/api/README.md`
2. `references/SDK_OVERVIEW.md`
3. `references/V2_MODELING_WORKFLOWS.md`
4. Specific pages under `references/docs/api/`
5. Supporting pages under `references/docs/core/`

## Typical v2 surface

```python
from simplecadapi import GraphSession, export_model_json, replay_model_json

with GraphSession() as session:
    ...

model_json = export_model_json(session)
rebuilt = replay_model_json(model_json)
print(len(rebuilt))
```
