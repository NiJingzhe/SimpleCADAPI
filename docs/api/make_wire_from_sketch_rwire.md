# make_wire_from_sketch_rwire

## API Definition

```python
def make_wire_from_sketch_rwire(sketch: Sketch, profile: int | str = 0, *, require_fully_constrained: bool = False, strict: bool = True, tolerance: float = 1e-07, max_iterations: int = 80) -> Wire
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_wire_from_sketch_rwire`

## Description

Promote a sketch profile to a concrete wire, solving internally. The promotion
map preserves the exact ordered `entity_id` to Edge correspondence. A Sketch
with `name="rect"` and profile `bottom` produces the tag
`sketch.rect.profile.bottom`; entity ID `right` produces
`sketch.rect.entity.right` with `topology_name` evidence.

Promotion fails if the kernel returns a different Edge count, because the SDK
does not guess correspondence from Edge order, geometry, or measurements.
