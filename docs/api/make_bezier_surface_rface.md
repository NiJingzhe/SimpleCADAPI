# make_bezier_surface_rface

## API Definition

```python
def make_bezier_surface_rface(control_points: Sequence[Sequence[Sequence[float]]], weights: Optional[Sequence[Sequence[float]]] = None, *, tag_prefix: Optional[str] = None) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_bezier_surface_rface`

## Description

Create a trimmed Face carrying a tensor-product Bezier surface.
