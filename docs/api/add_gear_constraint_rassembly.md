# add_gear_constraint_rassembly

## API Definition

```python
def add_gear_constraint_rassembly(assembly: Assembly, constraint_id: str, connector_a: ConnectorRef, connector_b: ConnectorRef, pitch_radius_a: float, pitch_radius_b: float, phase_offset: Optional[float] = None, name: Optional[str] = None) -> Assembly
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import add_gear_constraint_rassembly`

## Description

Couple two revolute axes as meshing gears with inverse rotation.
