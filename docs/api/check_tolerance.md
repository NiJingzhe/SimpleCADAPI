# check_tolerance

## API Definition

```python
def check_tolerance(value: ScalarLike, tolerance: ToleranceLike, *, method: ToleranceMethod = 'worst_case', name: str | None = None, tolerance_unit: UnitLike | None = None) -> ToleranceCheck
```

*Source: tolerance.py*

## Import Surface

- top-level: `from simplecadapi import check_tolerance`

## Description

Propagate and verify one Length or Angle requirement.

``tolerance_unit`` defaults to the target dimension's canonical unit. When
provided, it must be dimensionally compatible and is converted before the
comparison. Legacy unitless requirements remain supported when no unit is
supplied.
