# make_circle_rwire

## API Definition

```python
def make_circle_rwire(
    center: Tuple[float, float, float],
    radius: ScalarLike,
    normal: Tuple[float, float, float] = (0, 0, 1),
    *,
    tag_prefix: Optional[str] = None,
    edge_tag: Optional[str] = None,
) -> Wire
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_circle_rwire`

## Description

Create a circular wire. `tag_prefix` creates `<tag_prefix>.wire`, while
`edge_tag` supplies the final segment of `<tag_prefix>.edge.<edge_tag>` for its
single circular Edge, or the complete Edge tag when `tag_prefix` is omitted.
These topology tags are preserved only where a downstream operation has
complete, kernel-proven correspondence.
