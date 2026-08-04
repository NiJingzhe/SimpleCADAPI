# revolve_rsolid

## API Definition

```python
def revolve_rsolid(profile: Union[Wire, Face], axis: Tuple[float, float, float] = (0, 0, 1), angle: ScalarLike = 360, origin: Tuple[float, float, float] = (0, 0, 0), *, tag_prefix: Optional[str] = None, result_tag: Optional[str] = None, start_face_tag: Optional[str] = None, end_face_tag: Optional[str] = None, side_faces_tag: Optional[str] = None) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import revolve_rsolid`

## Description

Create a revolved solid, with optional kernel-role-based tags.
