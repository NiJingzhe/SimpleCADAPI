# AssemblyBuildResult

## Class Definition

```python
class AssemblyBuildResult(value: Assembly, definition: AssemblyDefinition, model_json: str, solve_report: AssemblySolveReport, artifact_paths: Mapping[str, Path] = field(default_factory=dict))
```

*Source: build/results.py*

## Import Surface

- top-level: `from simplecadapi import AssemblyBuildResult`

## Description

Runtime Assembly plus its external-reference durable definition.
