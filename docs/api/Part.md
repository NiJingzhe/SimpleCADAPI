# Part

## Class Definition

```python
class Part(part_id: str, body: Solid, name: Optional[str] = None, material: Optional[Material] = None, connectors: Tuple[Connector, ...] = ())
```

*Source: product.py*

## Import Surface

- top-level: `from simplecadapi import Part`

## Description

Single-body product item wrapping exactly one Solid.
