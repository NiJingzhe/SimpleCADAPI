# make_face_from_sketch_rface

## API Definition

```python
def make_face_from_sketch_rface(sketch: Sketch, profile: int | str = 0, *, require_fully_constrained: bool = False, strict: bool = True, tolerance: float = 1e-07, max_iterations: int = 80) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_face_from_sketch_rface`

## Description

Promote a sketch profile to a concrete face, solving internally.
