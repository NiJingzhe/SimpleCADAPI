# make_ellipse_rwire

## API Definition

```python
def make_ellipse_rwire(center: Tuple[float, float, float], major_radius: ScalarLike, minor_radius: ScalarLike, normal: Tuple[float, float, float] = (0, 0, 1), *, major_direction: Optional[Tuple[float, float, float]] = None, tag_prefix: Optional[str] = None, edge_tag: Optional[str] = None) -> Wire
```

*Source: operators/geometry.py*

## Import Surface

- top-level: `from simplecadapi import make_ellipse_rwire`

## Description

Create an elliptical wire.
