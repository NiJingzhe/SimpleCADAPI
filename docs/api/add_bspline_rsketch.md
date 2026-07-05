# add_bspline_rsketch

## API Definition

```python
def add_bspline_rsketch(sketch: Sketch, entity_id: str, start: Union[SketchRef, str], end: Union[SketchRef, str], control_points: Sequence[Sequence[float]], degree: int = 3, knots: Optional[Sequence[float]] = None, multiplicities: Optional[Sequence[int]] = None, weights: Optional[Sequence[float]] = None, periodic: bool = False, *, construction: bool = False) -> Sketch
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import add_bspline_rsketch`

## Description

Add a B-spline curve entity to a sketch.

The start/end point refs link the B-spline into a closed profile
loop.  Control points are stored as literal 2-D coordinates.
