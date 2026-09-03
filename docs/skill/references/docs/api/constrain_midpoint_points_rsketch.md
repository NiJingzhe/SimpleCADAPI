# constrain_midpoint_points_rsketch

## API Definition

```python
def constrain_midpoint_points_rsketch(sketch: Sketch, mid: Union[SketchRef, str], a: Union[SketchRef, str], b: Union[SketchRef, str], *, constraint_id: Optional[str] = None) -> Sketch
```

*Source: operators/sketch.py*

## Import Surface

- top-level: `from simplecadapi import constrain_midpoint_points_rsketch`

## Description

Constrain point ``mid`` to be the midpoint of points ``a`` and ``b``.
