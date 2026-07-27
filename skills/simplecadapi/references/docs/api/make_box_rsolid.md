# make_box_rsolid

## API Definition

```python
def make_box_rsolid(
    width: ScalarLike,
    height: ScalarLike,
    depth: ScalarLike,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
    *,
    tag_prefix: Optional[str] = None,
    result_tag: Optional[str] = None,
    bottom_face_tag: Optional[str] = None,
    top_face_tag: Optional[str] = None,
    front_face_tag: Optional[str] = None,
    back_face_tag: Optional[str] = None,
    left_face_tag: Optional[str] = None,
    right_face_tag: Optional[str] = None,
) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_box_rsolid`

## Description

Create a native box with six exact kernel-backed Face roles: `box.bottom`,
`box.top`, `box.front`, `box.back`, `box.left`, and `box.right`.
`tag_prefix="housing"` creates `housing.solid` and corresponding
`housing.face.<role>` topology-identity tags. Use the face tag arguments for
role tags and `result_tag` for the Solid.

Box Edge roles are unsupported because the current OCP builder does not expose
equivalent direct Edge witnesses. Select an exact Edge from two tagged incident
Faces with QL `incident_to(..., distinct=True)` or `shared_boundary(...)`.
