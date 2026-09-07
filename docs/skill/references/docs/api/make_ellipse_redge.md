# make_ellipse_redge

## API Definition

```python
def make_ellipse_redge(center: Tuple[float, float, float], major_radius: ScalarLike, minor_radius: ScalarLike, normal: Tuple[float, float, float] = (0, 0, 1), *, major_direction: Optional[Tuple[float, float, float]] = None, tag_prefix: Optional[str] = None) -> Edge
```

*Source: operators/geometry.py*

## Import Surface

- top-level: `from simplecadapi import make_ellipse_redge`

## Description

Create a full ellipse edge.

``major_direction`` orients the major axis in the ellipse plane; when
omitted the plane basis derived from ``normal`` picks it.
