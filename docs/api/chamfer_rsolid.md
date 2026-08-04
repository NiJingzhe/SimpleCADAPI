# chamfer_rsolid

## API Definition

```python
def chamfer_rsolid(solid: Solid, edges: Union[Sequence[Edge], ShapeSelector], distance: ScalarLike, *, result_tag: Optional[str] = None, generated_faces_tag: Optional[str] = None) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import chamfer_rsolid`

## Description

Apply chamfers, with optional tagging of kernel-proven patch faces.
