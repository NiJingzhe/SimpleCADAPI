# AssemblySolveReport

## Class Definition

```python
class AssemblySolveReport(mode: str, component_lookups: int, component_hits: int, component_misses: int, corrupt_entries: int, dirty_instances: tuple[str, ...] = (), geometry_dirty_instances: tuple[str, ...] = (), material_dirty_instances: tuple[str, ...] = (), binding_dirty_endpoints: tuple[str, ...] = (), dirty_connectors: tuple[str, ...] = (), dirty_relations: tuple[str, ...] = (), dirty_components: tuple[str, ...] = (), public_connector_changed: tuple[str, ...] = (), propagated_paths: tuple[str, ...] = (), component_results: tuple[ComponentSolveResult, ...] = ())
```

*Source: build/incremental_solver.py*

## Import Surface

- top-level: `from simplecadapi import AssemblySolveReport`

## Description

Structured incremental solve and dirty-propagation evidence.
