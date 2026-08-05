# fit_point_grid_rface

## API Definition

```python
def fit_point_grid_rface(points: Sequence[Sequence[Sequence[float]]], *, tolerance: float = 0.001, degree_min: int = 3, degree_max: int = 8, smoothing: Optional[Tuple[float, float, float]] = None, tag_prefix: Optional[str] = None) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import fit_point_grid_rface`

## Description

Fit a B-spline Face through a rectangular 3D point grid.
