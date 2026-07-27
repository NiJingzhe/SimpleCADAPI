# shell_rsolid

## API Definition

```python
def shell_rsolid(
    solid: Solid,
    faces_to_remove: Union[Sequence[Face], ShapeSelector],
    thickness: ScalarLike,
    *,
    result_tag: Optional[str] = None,
    body_faces_tag: Optional[str] = None,
    offset_faces_tag: Optional[str] = None,
    closing_faces_tag: Optional[str] = None,
    wall_edges_tag: Optional[str] = None,
) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import shell_rsolid`

## Description

Shell a solid to create a hollow part. The operation can expose these exact
kernel roles:

- `shell.body_face`: surviving or modified source body faces.
- `shell.offset_face`: generated offset faces.
- `shell.closing_descendant`: descendants of removed closing faces.
- `shell.wall`: generated closing-boundary edges.

The named arguments map directly to those roles. A role is available only when
OCC provides a complete witness;
requesting an unavailable role fails instead of deriving one from enumeration or
geometry. `result_tag` tags the resulting solid. Recorded assignments replay as
semantic nodes and preserve face versus edge target kinds.
