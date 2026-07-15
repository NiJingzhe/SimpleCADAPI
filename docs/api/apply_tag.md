# apply_tag

## API Definition

```python
def apply_tag(shape: AnyShape, tag: str) -> AnyShape
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import apply_tag`

## Description

Attach a normalized local user tag to a shape.

Tags must already be normalized lowercase tokens such as
`role.mounting_surface` or `group.fasteners`. The default topology policy is
`local` for every tag; token prefixes do not imply downward propagation.
Lineage visibility is limited to proven continuation and fragment witnesses.

`apply_tag(...)` preserves its historical in-place wrapper behavior. Use
`apply_tag_rselection(...)` when you need an independent semantic shape view,
explicit topology propagation, or a replayable multi-entity assignment.
