# make_wire_from_edges_rwire

## API Definition

```python
def make_wire_from_edges_rwire(edges: List[Edge], *, tag_prefix: Optional[str] = None) -> Wire
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_wire_from_edges_rwire`

## Description

Create a wire from a list of connected edges. Existing proven Edge topology
tags are preserved by exact topology identity; `tag_prefix` optionally adds
`<tag_prefix>.wire` to the resulting wire.
