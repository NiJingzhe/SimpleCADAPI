# make_face_from_sketch_rface

## API Definition

```python
def make_face_from_sketch_rface(sketch: Sketch, profile: int | str = 0, *, inner_profiles: Sequence[int | str] = (), require_fully_constrained: bool = False, strict: bool = True, tolerance: float = 1e-07, max_iterations: int = 80) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_face_from_sketch_rface`

## Description

Promote an outer sketch profile and optional explicitly selected inner profiles
to a concrete face, solving internally. Pass hole loops through
`inner_profiles=(...)`. The Face and
each boundary Edge receive canonical tags with `topology_name` evidence from the
exact Sketch promotion map. For a Sketch with `name="rect"`, profile `bottom`,
and entity ID `right`, the tags are `sketch.rect.profile.bottom` and
`sketch.rect.entity.right`.

The bindings replay from the Sketch payload and promotion parameters. Legacy
compatibility tags such as `sketch_entity.right` remain separate from the
canonical topology-identity tags.
