# ModelResult

## Class Definition

```python
class ModelResult(value: Any, session: GraphSession, result_node_ids: Tuple[str, ...], model_json: str, session_json: str, artifact_paths: Mapping[str, Path] = field(default_factory=dict))
```

*Source: graph.py*

## Import Surface

- top-level: `from simplecadapi import ModelResult`

## Description

The value and durable graph artifacts produced by ``@model``.
