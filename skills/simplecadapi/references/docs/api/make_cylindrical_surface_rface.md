# make_cylindrical_surface_rface

## API Definition

```python
def make_cylindrical_surface_rface(radius: ScalarLike, u_range: Tuple[ScalarLike, ScalarLike], v_range: Tuple[ScalarLike, ScalarLike], origin: Tuple[float, float, float] = (0, 0, 0), axis: Tuple[float, float, float] = (0, 0, 1), x_direction: Optional[Tuple[float, float, float]] = None, *, tolerance: ScalarLike = 1e-07, tag_prefix: Optional[str] = None) -> Face
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_cylindrical_surface_rface`

## Description

Create a finite cylindrical carrier Face over explicit U/V ranges.

``radius``, V values, and ``tolerance`` use model length units. U values
are unitless raw radians, must increase, and may span at most one
revolution. Unit-aware angle expressions are not accepted for U because
the existing expression evaluator returns canonical angles in degrees.
