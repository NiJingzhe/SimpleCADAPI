# constrain_diameter_rsketch

## API Definition

```python
def constrain_diameter_rsketch(sketch: Sketch, circle: Union[SketchRef, str], value: ScalarLike, *, constraint_id: Optional[str] = None, driving: bool = True) -> Sketch
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import constrain_diameter_rsketch`

## Description

Add a driving or reference diameter constraint to a sketch circle or circular arc.
