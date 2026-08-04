# make_interpolated_spline_redge

## API Definition

```python
def make_interpolated_spline_redge(*, points: Sequence[Sequence[ScalarLike]], periodic: bool = False, tolerance: ScalarLike = 1e-06) -> Edge
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_interpolated_spline_redge`

## Description

Interpolate an exact B-spline edge through the supplied points.
