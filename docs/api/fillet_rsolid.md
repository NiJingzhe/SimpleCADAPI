# fillet_rsolid

## API Definition

```python
def fillet_rsolid(
    solid: Solid,
    edges: Union[Sequence[Edge], ShapeSelector],
    radius: ScalarLike,
    *,
    output_tags: Optional[Mapping[str, str]] = None,
    result_tag: Optional[str] = None,
    generated_faces_tag: Optional[str] = None,
) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import fillet_rsolid`

## Description

Apply fillets to selected solid edges. `generated_faces_tag` targets every face
with the kernel-proven `fillet.patch` role. The same assignment can be supplied as
`output_tags={"fillet.patch": "role.label_surface"}`. OCC contour expansion is
included, so the role is not limited to the original seed edge.

The operation fails if a requested patch role has no proven result. `result_tag`
tags the resulting solid. In a `GraphSession`, assignments are separate replayable
semantic nodes with asserted user provenance.
