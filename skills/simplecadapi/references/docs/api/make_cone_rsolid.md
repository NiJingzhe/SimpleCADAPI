# make_cone_rsolid

## API Definition

```python
def make_cone_rsolid(bottom_radius: ScalarLike, height: ScalarLike, top_radius: ScalarLike = 0.0, bottom_face_center: Tuple[float, float, float] = (0, 0, 0), axis: Tuple[float, float, float] = (0, 0, 1), *, tag_prefix: Optional[str] = None, result_tag: Optional[str] = None, start_face_tag: Optional[str] = None, end_face_tag: Optional[str] = None, side_face_tag: Optional[str] = None, start_edge_tag: Optional[str] = None, end_edge_tag: Optional[str] = None, seam_edge_tag: Optional[str] = None) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_cone_rsolid`

## Description

Create a cone or frustum with native kernel-backed topology tags.
