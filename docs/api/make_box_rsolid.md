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

Create a native box solid. The exact kernel-backed Face roles are `box.bottom`,
`box.top`, `box.front`, `box.back`, `box.left`, and `box.right`. Each role has
exactly one Face.

The face tag arguments attach tags to those roles. `result_tag` targets the
result Solid. `tag_prefix="housing"` creates the topology tags
`housing.solid`, `housing.face.bottom`,
`housing.face.top`, `housing.face.front`, `housing.face.back`,
`housing.face.left`, and `housing.face.right`.

The roles and topology tags come directly from OCC Box Face witnesses, not Face
enumeration or geometric classification. The current OCP Box builder does not
expose equivalent direct Edge witnesses, so Box Edge output roles are
unsupported. Select an exact Edge from two tagged incident Faces with
`Q.edges().incident_to(face_a, face_b, distinct=True)` or
`face_a.shared_boundary(face_b)`.
