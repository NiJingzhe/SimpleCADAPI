# make_interpolated_spline_rwire

## API Definition

```python
def make_interpolated_spline_rwire(*, points: Sequence[Sequence[ScalarLike]], periodic: bool = False, tolerance: ScalarLike = 1e-06) -> Wire
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_interpolated_spline_rwire`

## Description

Create a one-edge wire that interpolates the supplied points.
