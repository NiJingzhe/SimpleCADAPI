# make_line_redge

## API Definition

```python
def make_line_redge(
    start: Tuple[ScalarLike, ScalarLike, ScalarLike],
    end: Tuple[ScalarLike, ScalarLike, ScalarLike],
    *,
    tag_prefix: Optional[str] = None,
) -> Edge
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_line_redge`

## Description

Create a straight edge between two points. When `tag_prefix` is provided, the
edge receives the topology tag `<tag_prefix>.edge`. Downstream profile and
feature operations may preserve that tag when kernel history proves the
correspondence.
