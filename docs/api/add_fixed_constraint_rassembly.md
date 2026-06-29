# add_fixed_constraint_rassembly

## API Definition

```python
def add_fixed_constraint_rassembly(assembly: Assembly, constraint_id: str, connector_a: ConnectorRef, connector_b: ConnectorRef, name: Optional[str] = None) -> Assembly
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import add_fixed_constraint_rassembly`

## Description

Constrain two component connectors to the same frame.
