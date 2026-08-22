# ToleranceAnalysis

## Class Definition

```python
class ToleranceAnalysis(target_expr_id: str, method: ToleranceMethod, nominal: float, lower_bound: float, upper_bound: float, lower_deviation: float, upper_deviation: float, dimension: Dimension | None = None, unit: Unit | None = None, contributions: Tuple[ToleranceContribution, ...] = ())
```

*Source: tolerance.py*

## Import Surface

- top-level: `from simplecadapi import ToleranceAnalysis`

## Description

Nominal value and propagated limits for an expression.
