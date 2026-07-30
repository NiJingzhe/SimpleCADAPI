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
`inner_profiles=(...)`. The promoted
Face receives the canonical profile topology-identity tag and each boundary
Edge receives the exact Sketch entity tag from the promotion map. For example,
a Sketch with `name="rect"` and profile `bottom` produces `sketch.rect.profile.bottom` and
`sketch.rect.entity.bottom`.

These are creation-time tags with `topology_name` evidence backed by the solved Sketch
promotion map. They replay from the Sketch payload and promotion parameters;
ordinary compatibility tags such as `sketch_entity.bottom` remain separate.
