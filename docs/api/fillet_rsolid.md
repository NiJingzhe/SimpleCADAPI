# fillet_rsolid

## API Definition

```python
def fillet_rsolid(solid: Solid, edges: Union[Sequence[Edge], ShapeSelector], radius: ScalarLike) -> Solid
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import fillet_rsolid`

## Description

Apply fillets to selected solid edges.
