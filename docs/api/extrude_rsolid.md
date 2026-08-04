# extrude_rsolid

## API Definition

```python
def extrude_rsolid(profile: Union[Wire, Face], direction: Tuple[float, float, float], distance: ScalarLike, *, tag_prefix: Optional[str] = None, result_tag: Optional[str] = None, start_face_tag: Optional[str] = None, end_face_tag: Optional[str] = None, side_faces_tag: Optional[str] = None) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import extrude_rsolid`

## Description

Create a solid by extruding a profile, with optional role-based tags.
