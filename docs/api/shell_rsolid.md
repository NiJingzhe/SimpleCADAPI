# shell_rsolid

## API Definition

```python
def shell_rsolid(solid: Solid, faces_to_remove: Union[Sequence[Face], ShapeSelector], thickness: ScalarLike) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import shell_rsolid`

## Description

Shell a solid to create a hollow part.
