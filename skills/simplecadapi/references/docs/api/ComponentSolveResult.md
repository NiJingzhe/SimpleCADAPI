# ComponentSolveResult

## Class Definition

```python
class ComponentSolveResult(component_id: str, solve_key: str, instance_ids: tuple[str, ...], relation_ids: tuple[str, ...], cache_hit: bool, solved: bool, miss_reason: str | None = None)
```

*Source: build/incremental_solver.py*

## Import Surface

- top-level: `from simplecadapi import ComponentSolveResult`

## Description

Cache and residual outcome for one connected constraint component.
