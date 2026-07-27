# make_rectangle_rwire

## API Definition

```python
def make_rectangle_rwire(
    width: ScalarLike,
    height: ScalarLike,
    center: Tuple[ScalarLike, ScalarLike, ScalarLike] = (0, 0, 0),
    normal: Tuple[ScalarLike, ScalarLike, ScalarLike] = (0, 0, 1),
    *,
    tag_prefix: Optional[str] = None,
    edge_tags: Optional[Sequence[str]] = None,
) -> Wire
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_rectangle_rwire`

## Description

Create a rectangular wire. `tag_prefix` creates `<tag_prefix>.wire`.
`edge_tags` must contain one tag for each generated profile Edge, in kernel
construction order. With `tag_prefix`, each value is the local segment of
`<tag_prefix>.edge.<edge_tag>`; without it, each value is the complete Edge tag.
These topology tags are stable anchors for operations such as `extrude_rsolid`
when correspondence is proven.
