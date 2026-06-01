# make_cone_rsolid

## API Definition

```python
def make_cone_rsolid(bottom_radius: ScalarLike, height: ScalarLike, top_radius: ScalarLike = 0.0, bottom_face_center: Tuple[float, float, float] = (0, 0, 0), axis: Tuple[float, float, float] = (0, 0, 1)) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_cone_rsolid`

## Description

Create a cone or truncated cone solid.
