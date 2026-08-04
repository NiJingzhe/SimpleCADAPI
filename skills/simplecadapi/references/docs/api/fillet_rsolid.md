# fillet_rsolid

## API Definition

```python
def fillet_rsolid(solid: Solid, edges: Union[Sequence[Edge], ShapeSelector], radius: ScalarLike, *, result_tag: Optional[str] = None, generated_faces_tag: Optional[str] = None) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import fillet_rsolid`

## Description

Apply fillets, with optional tagging of kernel-proven patch faces.
