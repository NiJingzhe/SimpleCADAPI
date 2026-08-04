# constrain_tangent_rsketch

## API Definition

```python
def constrain_tangent_rsketch(sketch: Sketch, a: Union[SketchRef, str], b: Union[SketchRef, str], *, at_a: Optional[str] = None, at_b: Optional[str] = None, mode: str = 'external', constraint_id: Optional[str] = None) -> Sketch
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import constrain_tangent_rsketch`

## Description

Constrain supported curves to be tangent on an explicit branch.

``at_a``/``at_b`` select ``"start"`` or ``"end"`` for arc and
B-spline endpoint tangency. Circle-circle tangency accepts
``mode="external"`` or ``mode="internal"``.
