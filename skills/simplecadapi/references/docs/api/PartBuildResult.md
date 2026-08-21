# PartBuildResult

## Class Definition

```python
class PartBuildResult(value: Part, definition: PartDefinition, feature_graph: FeatureGraphArtifact, cache_report: CacheReport, interface_diff: PartInterfaceDiff | None = None)
```

*Source: build/results.py*

## Import Surface

- top-level: `from simplecadapi import PartBuildResult`

## Description

Runtime Part plus its durable definition, feature DAG, and cache evidence.
