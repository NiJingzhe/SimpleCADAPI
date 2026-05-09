# V2 Modeling Workflows

## 1) Capture a replayable v2 modeling flow

```python
from simplecadapi import GraphSession, export_model_json

with GraphSession() as session:
    ...

payload = export_model_json(session)
```

## 2) Import and use in Python

```python
import simplecadapi as scad
from simplecadapi import GraphSession, export_model_json
```

## 3) Keep replay payloads as the interchange boundary

- Prefer `export_model_json()` output instead of hand-written payloads.
- Use `replay_model_json()` when you need deterministic reconstruction.
- Use `import_model_json()` when consuming previously exported payloads.
