# constrain_symmetric_rsketch

## API Definition

```python
def constrain_symmetric_rsketch(sketch: Sketch, a: Union[SketchRef, str], b: Union[SketchRef, str], axis: Union[SketchRef, str], *, constraint_id: Optional[str] = None) -> Sketch
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import constrain_symmetric_rsketch`

## Description

Constrain two sketch points to be symmetric about a line axis.
