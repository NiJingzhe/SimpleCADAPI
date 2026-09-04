# constrain_mirror_rsketch

## API Definition

```python
def constrain_mirror_rsketch(sketch: Sketch, a: Union[SketchRef, str], axis: Union[SketchRef, str], b: Union[SketchRef, str], *, constraint_id: Optional[str] = None) -> Sketch
```

*Source: operators/sketch.py*

## Import Surface

- top-level: `from simplecadapi import constrain_mirror_rsketch`

## Description

Constrain two same-kind entities to be mirror images about a line.

Lines match endpoints by nearest initial position; circles match centers;
arcs match endpoints and centers.
