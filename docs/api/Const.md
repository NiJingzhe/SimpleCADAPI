# Const

## Class Definition

```python
class Const(value: float, expr_id: str = field(default_factory=lambda : _make_expr_id('const')))
```

*Source: expr.py*

## Import Surface

- top-level: `from simplecadapi import Const`

## Description

Immutable constant node used in the v2 expression graph.
