# constrain_major_radius_rsketch

## API Definition

```python
def constrain_major_radius_rsketch(sketch: Sketch, ellipse: Union[SketchRef, str], value: ScalarLike, *, constraint_id: Optional[str] = None, driving: bool = True) -> Sketch
```

*Source: operators/sketch.py*

## Import Surface

- top-level: `from simplecadapi import constrain_major_radius_rsketch`

## Description

Add a driving major-radius constraint to a sketch ellipse.
