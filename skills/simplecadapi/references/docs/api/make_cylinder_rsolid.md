# make_cylinder_rsolid

## API Definition

```python
def make_cylinder_rsolid(
    radius: ScalarLike,
    height: ScalarLike,
    bottom_face_center: Tuple[float, float, float] = (0, 0, 0),
    axis: Tuple[float, float, float] = (0, 0, 1),
    *,
    tag_prefix: Optional[str] = None,
    result_tag: Optional[str] = None,
    start_face_tag: Optional[str] = None,
    end_face_tag: Optional[str] = None,
    side_face_tag: Optional[str] = None,
    start_edge_tag: Optional[str] = None,
    end_edge_tag: Optional[str] = None,
    seam_edge_tag: Optional[str] = None,
) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_cylinder_rsolid`

## Description

Create a native cylinder with kernel-backed topology tags. `tag_prefix="shaft"` produces
`shaft.face.start`, `shaft.face.end`, `shaft.face.side`, and corresponding
`shaft.edge.start`, `shaft.edge.end`, and `shaft.edge.seam` tags. Face tags
are inherited by their boundary Edges. Role tags use the native
`cylinder.*` Face/Edge roles. Use QL `incident_to(..., distinct=True)` or
`shared_boundary(...)` to select an Edge from its two neighboring tagged Faces.
