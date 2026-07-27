# analyze_tolerance

## API Definition

```python
def analyze_tolerance(value: ScalarLike, *, method: ToleranceMethod = 'worst_case') -> ToleranceAnalysis
```

*Source: tolerance.py*

## Import Surface

- top-level: `from simplecadapi import analyze_tolerance`

## Description

Propagate source manufacturing tolerances through a scalar expression.

``worst_case`` returns guaranteed interval bounds. Affine chains are
dependency-aware, so repeated variables such as ``x - x`` cancel exactly;
nonlinear chains use conservative interval arithmetic. ``rss`` performs a
first-order root-sum-square calculation using analytic sensitivities.

Unit-aware variables are converted to canonical CAD units before
propagation. The returned analysis reports the inferred physical dimension
and canonical result unit. Every variable in the expression must declare a
source tolerance.
