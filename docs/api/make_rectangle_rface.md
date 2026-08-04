# make_rectangle_rface

## API Definition

```python
def make_rectangle_rface(width: ScalarLike, height: ScalarLike, center: Tuple[ScalarLike, ScalarLike, ScalarLike] = (0, 0, 0), normal: Tuple[ScalarLike, ScalarLike, ScalarLike] = (0, 0, 1), *, tag_prefix: Optional[str] = None, edge_tags: Optional[Sequence[str]] = None) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_rectangle_rface`

## Description

Create a rectangular face.
