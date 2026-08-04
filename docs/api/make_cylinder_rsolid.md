# make_cylinder_rsolid

## API Definition

```python
def make_cylinder_rsolid(radius: ScalarLike, height: ScalarLike, bottom_face_center: Tuple[float, float, float] = (0, 0, 0), axis: Tuple[float, float, float] = (0, 0, 1), *, tag_prefix: Optional[str] = None, result_tag: Optional[str] = None, start_face_tag: Optional[str] = None, end_face_tag: Optional[str] = None, side_face_tag: Optional[str] = None, start_edge_tag: Optional[str] = None, end_edge_tag: Optional[str] = None, seam_edge_tag: Optional[str] = None) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_cylinder_rsolid`

## Description

Create a cylinder with native kernel-backed Face and Edge topology tags.
