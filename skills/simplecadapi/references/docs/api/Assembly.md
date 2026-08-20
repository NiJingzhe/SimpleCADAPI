# Assembly

## Class Definition

```python
class Assembly(assembly_id: str, name: Optional[str] = None, components: Tuple[Component, ...] = (), public_connectors: Tuple[PublicConnectorRef, ...] = (), constraints: Tuple[Constraint, ...] = (), grounded_component_ids: Tuple[str, ...] = ())
```

*Source: assembly.py*

## Import Surface

- top-level: `from simplecadapi import Assembly`

## Description

Product structure containing placed Part or subassembly components.
