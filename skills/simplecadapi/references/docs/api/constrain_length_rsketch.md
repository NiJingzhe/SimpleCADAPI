# constrain_length_rsketch

## API Definition

```python
def constrain_length_rsketch(sketch: Sketch, line: Union[SketchRef, str], value: ScalarLike, *, constraint_id: Optional[str] = None, driving: bool = True) -> Sketch
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import constrain_length_rsketch`

## Description

Add a driving line length constraint.
