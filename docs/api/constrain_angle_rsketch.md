# constrain_angle_rsketch

## API Definition

```python
def constrain_angle_rsketch(sketch: Sketch, a: Union[SketchRef, str], b: Union[SketchRef, str], value: ScalarLike, *, constraint_id: Optional[str] = None, driving: bool = True) -> Sketch
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import constrain_angle_rsketch`

## Description

Add a driving angle constraint between two sketch lines.
