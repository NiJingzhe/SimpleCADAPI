# make_box_rsolid

## API Definition

```python
def make_box_rsolid(width: ScalarLike, height: ScalarLike, depth: ScalarLike, bottom_face_center: Tuple[float, float, float] = (0, 0, 0), *, tag_prefix: Optional[str] = None, result_tag: Optional[str] = None, bottom_face_tag: Optional[str] = None, top_face_tag: Optional[str] = None, front_face_tag: Optional[str] = None, back_face_tag: Optional[str] = None, left_face_tag: Optional[str] = None, right_face_tag: Optional[str] = None) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_box_rsolid`

## Description

Create a box with native kernel-backed Face topology tags.
