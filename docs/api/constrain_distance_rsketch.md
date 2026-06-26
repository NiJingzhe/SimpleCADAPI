# constrain_distance_rsketch

## API Definition

```python
def constrain_distance_rsketch(sketch: Sketch, a: Union[SketchRef, str], b: Union[SketchRef, str], value: ScalarLike, *, constraint_id: Optional[str] = None, driving: bool = True) -> Sketch
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import constrain_distance_rsketch`

## Description

Add a driving point-to-point distance constraint.
