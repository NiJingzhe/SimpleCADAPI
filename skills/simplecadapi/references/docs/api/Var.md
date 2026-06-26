# Var

## Class Definition

```python
class Var(name: str, default: float, comment: str | None = None, expr_id: str = field(default_factory=lambda : _make_expr_id('var')))
```

*Source: expr.py*

## Import Surface

- top-level: `from simplecadapi import Var`

## Description

Named scalar parameter with a default fallback value.
