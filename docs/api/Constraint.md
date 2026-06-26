# Constraint

## Class Definition

```python
class Constraint(constraint_id: str, constraint_kind: ConstraintKind, connector_a: ConnectorRef, connector_b: ConnectorRef, drive_distance: Optional[float] = None, distance_limit: Optional[ScalarLimit] = None, drive_angle_degrees: Optional[float] = None, angle_limit: Optional[ScalarLimit] = None, name: Optional[str] = None)
```

*Source: product.py*

## Import Surface

- top-level: `from simplecadapi import Constraint`

## Description

Connector-to-connector assembly constraint.
