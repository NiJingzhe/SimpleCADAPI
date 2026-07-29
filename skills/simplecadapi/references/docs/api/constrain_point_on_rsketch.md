# constrain_point_on_rsketch

## API Definition

```python
def constrain_point_on_rsketch(sketch: Sketch, point: Union[SketchRef, str], entity: Union[SketchRef, str], *, constraint_id: Optional[str] = None) -> Sketch
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import constrain_point_on_rsketch`

## Description

Constrain a sketch point to lie on a line, circle, or circular arc. For arcs, the solver enforces the supporting-circle radius; endpoint/sweep membership remains part of the sketch profile validation.
