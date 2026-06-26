# Assembly

## Class Definition

```python
class Assembly(assembly_id: str, name: Optional[str] = None, components: Tuple[Component, ...] = (), connectors: Tuple[Connector, ...] = (), constraints: Tuple[Constraint, ...] = (), grounded_component_ids: Tuple[str, ...] = ())
```

*Source: product.py*

## Import Surface

- top-level: `from simplecadapi import Assembly`

## Description

Product structure containing placed Part or subassembly components.
