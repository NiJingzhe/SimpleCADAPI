# Var

## Class Definition

```python
class Var(name: str, default: float, comment: str | None = None, expr_id: str = field(default_factory=lambda : _make_expr_id('var')), tolerance: DimensionTolerance | None = None, unit: Unit | None = None, tolerance_unit: Unit | None = None)
```

*Source: expr.py*

## Import Surface

- top-level: `from simplecadapi import Var`

## Description

Named scalar parameter with optional physical-unit and tolerance intent.

``default`` and ``tolerance`` remain in their declared units. Evaluation,
geometry parameters, and tolerance propagation convert them to SimpleCAD's
canonical CAD units: millimeters for length and degrees for angle.
