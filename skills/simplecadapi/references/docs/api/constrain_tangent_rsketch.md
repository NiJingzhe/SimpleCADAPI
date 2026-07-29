# constrain_tangent_rsketch

## API Definition

```python
def constrain_tangent_rsketch(sketch: Sketch, a: Union[SketchRef, str], b: Union[SketchRef, str], *, at_a: Optional[str] = None, at_b: Optional[str] = None, mode: str = "external", constraint_id: Optional[str] = None) -> Sketch
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import constrain_tangent_rsketch`

## Description

Constrain lines, circles, circular arcs, and cubic B-spline endpoints to be tangent. Arc/B-spline endpoint tangency requires `at_a` or `at_b` set to `"start"` or `"end"`. Circle-circle tangency supports `mode="external"` and `mode="internal"`.
