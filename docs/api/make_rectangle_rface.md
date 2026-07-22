# make_rectangle_rface

## API Definition

```python
def make_rectangle_rface(
    width: ScalarLike,
    height: ScalarLike,
    center: Tuple[ScalarLike, ScalarLike, ScalarLike] = (0, 0, 0),
    normal: Tuple[ScalarLike, ScalarLike, ScalarLike] = (0, 0, 1),
    *,
    tag_prefix: Optional[str] = None,
    edge_tags: Optional[Sequence[str]] = None,
) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_rectangle_rface`

## Description

Create a rectangular face. `tag_prefix` creates `<tag_prefix>.face`, and
`edge_tags` supplies one tag for each of its four boundary Edges. With
`tag_prefix`, each is a local segment under `<tag_prefix>.edge`; without it,
each is a complete Edge tag. These topology tags can be projected to proven
feature Faces and queried with the same `list_tags(...)` and `ql.tag(...)`
surfaces as other tags.
