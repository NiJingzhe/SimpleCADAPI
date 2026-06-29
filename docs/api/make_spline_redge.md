# make_spline_redge

## API Definition

```python
def make_spline_redge(*, control_points: Sequence[Sequence[ScalarLike]], degree: int = 3, knots: Optional[Sequence[ScalarLike]] = None, multiplicities: Optional[Sequence[int]] = None, weights: Optional[Sequence[ScalarLike]] = None, periodic: bool = False) -> Edge
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_spline_redge`

## Description

Create an exact B-spline edge from named control-point parameters.

Pass sampled curve points through `fit_cubic_bspline_control_points(...)` first,
then pass the result fields explicitly as `control_points=...`, `knots=...`,
and `multiplicities=...`. `control_points` are poles, not interpolation
points; the curve generally does not pass through interior poles.
