# loft_rsolid

## API Definition

```python
def loft_rsolid(profiles: List[Wire], ruled: bool = False, *, tracking_policy: TrackingPolicy | str = TrackingPolicy.FULL, tag_prefix: Optional[str] = None, result_tag: Optional[str] = None, start_face_tag: Optional[str] = None, end_face_tag: Optional[str] = None, side_faces_tag: Optional[str] = None) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import loft_rsolid`

## Description

Create a lofted solid, with optional kernel-role-based tags.
