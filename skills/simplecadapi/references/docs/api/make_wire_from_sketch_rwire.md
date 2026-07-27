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
map preserves exact ordered entity-to-Edge correspondence and creates tags with
`topology_name` evidence, such as `sketch.rect.profile.bottom` and
`sketch.rect.entity.right`.

Promotion fails when the generated Edge count does not match the promotion map;
the SDK does not infer identity from geometry or enumeration heuristics.
