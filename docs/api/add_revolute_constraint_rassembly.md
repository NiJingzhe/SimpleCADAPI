# add_revolute_constraint_rassembly

## API Definition

```python
def add_revolute_constraint_rassembly(assembly: Assembly, constraint_id: str, connector_a: ConnectorRef, connector_b: ConnectorRef, drive_angle_degrees: Optional[float] = None, angle_limit: Optional[ScalarLimit] = None, name: Optional[str] = None) -> Assembly
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import add_revolute_constraint_rassembly`

## Description

Constrain two connectors as a revolute axis pair.
