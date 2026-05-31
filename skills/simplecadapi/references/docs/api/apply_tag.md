# apply_tag

## API Definition

```python
def apply_tag(shape: AnyShape, tag: str) -> AnyShape
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import apply_tag`

## Description

Attach a normalized tag to a shape using the standard propagation policy.

Tags must already be normalized lowercase tokens such as
``role.mounting_surface`` or ``group.fasteners``. Propagation is intentionally
not configurable from the public API; the default tag policy propagates
semantic role/anchor/group tags downward and keeps topology-specific tags
local.
