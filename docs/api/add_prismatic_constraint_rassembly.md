# add_prismatic_constraint_rassembly

## API Definition

```python
def add_prismatic_constraint_rassembly(assembly: Assembly, constraint_id: str, connector_a: ConnectorRef, connector_b: ConnectorRef, drive_distance: Optional[float] = None, distance_limit: Optional[ScalarLimit] = None, name: Optional[str] = None) -> Assembly
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import add_prismatic_constraint_rassembly`

## Description

Constrain two connectors as a prismatic slider pair.
