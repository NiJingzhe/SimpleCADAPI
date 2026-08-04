# shell_rsolid

## API Definition

```python
def shell_rsolid(solid: Solid, faces_to_remove: Union[Sequence[Face], ShapeSelector], thickness: ScalarLike, *, result_tag: Optional[str] = None, body_faces_tag: Optional[str] = None, offset_faces_tag: Optional[str] = None, closing_faces_tag: Optional[str] = None, wall_edges_tag: Optional[str] = None) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import shell_rsolid`

## Description

Shell a solid, with optional kernel-role-based face tags.
