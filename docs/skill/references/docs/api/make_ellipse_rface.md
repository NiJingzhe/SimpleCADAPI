# make_ellipse_rface

## API Definition

```python
def make_ellipse_rface(center: Tuple[float, float, float], major_radius: ScalarLike, minor_radius: ScalarLike, normal: Tuple[float, float, float] = (0, 0, 1), *, major_direction: Optional[Tuple[float, float, float]] = None, tag_prefix: Optional[str] = None, edge_tag: Optional[str] = None) -> Face
```

*Source: operators/geometry.py*

## Import Surface

- top-level: `from simplecadapi import make_ellipse_rface`

## Description

Create an elliptical face.
