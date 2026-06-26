# Expr

## Class Definition

```python
class Expr(op: str, args: Tuple[ScalarExpr, ...], expr_id: str = field(default_factory=lambda : _make_expr_id('expr')))
```

*Source: expr.py*

## Import Surface

- top-level: `from simplecadapi import Expr`

## Description

Derived scalar expression node built from one or more operands.
