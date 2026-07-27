# make_circle_rface

## API Definition

```python
def make_circle_rface(
    center: Tuple[float, float, float],
    radius: ScalarLike,
    normal: Tuple[float, float, float] = (0, 0, 1),
    *,
    tag_prefix: Optional[str] = None,
    edge_tag: Optional[str] = None,
) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_circle_rface`

## Description

Create a circular face. `tag_prefix` creates `<tag_prefix>.face`, while
`edge_tag` supplies the final segment of `<tag_prefix>.edge.<edge_tag>` for its
boundary Edge, or the complete Edge tag when `tag_prefix` is omitted. The Face
topology tag is visible to effective boundary-Edge QL queries without copying
arbitrary local Face tags to every Edge.
