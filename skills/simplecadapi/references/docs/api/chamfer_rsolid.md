# chamfer_rsolid

## API Definition

```python
def chamfer_rsolid(
    solid: Solid,
    edges: Union[Sequence[Edge], ShapeSelector],
    distance: ScalarLike,
    *,
    result_tag: Optional[str] = None,
    generated_faces_tag: Optional[str] = None,
) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import chamfer_rsolid`

## Description

Apply chamfers to selected solid edges. `generated_faces_tag` targets every face
with the kernel-proven `chamfer.patch` role. OCC contour expansion is included
rather than treating only the seed edge as the feature boundary.

The operation fails if a requested patch role has no proven result. `result_tag`
tags the resulting solid, and graph recording lowers assignments to replayable
semantic nodes.
