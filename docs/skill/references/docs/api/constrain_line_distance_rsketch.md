# constrain_line_distance_rsketch

## API Definition

```python
def constrain_line_distance_rsketch(sketch: Sketch, a: Union[SketchRef, str], b: Union[SketchRef, str], value: ScalarLike, *, constraint_id: Optional[str] = None, driving: bool = True) -> Sketch
```

*Source: operators/sketch.py*

## Import Surface

- top-level: `from simplecadapi import constrain_line_distance_rsketch`

## Description

Add a driving minimum-distance constraint between two sketch lines.

The constraint drives the distance from line ``a``'s start point to line
``b``; for parallel lines this is exactly the minimum distance between
them. The solved point keeps its initial side of line ``b``.
