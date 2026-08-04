# sweep_rsolid

## API Definition

```python
def sweep_rsolid(profile: Face, path: Wire, is_frenet: bool = False, *, tag_prefix: Optional[str] = None, result_tag: Optional[str] = None, start_face_tag: Optional[str] = None, end_face_tag: Optional[str] = None, side_faces_tag: Optional[str] = None) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import sweep_rsolid`

## Description

Create a swept solid, with optional kernel-role-based tags.
