# PartBuildResult

## Class Definition

```python
class PartBuildResult(value: Part, definition: PartDefinition, session: GraphSession, result_node_ids: tuple[str, ...], model_json: str, session_json: str, cache_report: CacheReport, interface_diff: PartInterfaceDiff | None = None, artifact_paths: Mapping[str, Path] = field(default_factory=dict))
```

*Source: build/results.py*

## Import Surface

- top-level: `from simplecadapi import PartBuildResult`

## Description

Runtime Part plus its durable definition, graph, and cache evidence.
