# add_rack_pinion_constraint_rassembly

## API Definition

```python
def add_rack_pinion_constraint_rassembly(assembly: Assembly, constraint_id: str, rack_connector: ConnectorRef, pinion_connector: ConnectorRef, pitch_radius: float, phase_offset: Optional[float] = None, name: Optional[str] = None) -> Assembly
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import add_rack_pinion_constraint_rassembly`

## Description

Couple a prismatic rack axis to a revolute pinion axis.
