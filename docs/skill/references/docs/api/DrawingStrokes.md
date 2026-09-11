# DrawingStrokes

## Class Definition

```python
class DrawingStrokes(source: str, page: int, rotation: int, width_pt: float, height_pt: float, total_primitives: int, matched: int, strokes: list[dict[str, Any]], stroke_color_census: dict[str, int], fill_color_census: dict[str, int], metadata: dict[str, Any] = field(default_factory=dict))
```

*Source: inspect/drawing/geometry.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.DrawingStrokes(...)`; unavailable inside GraphSession

## Description

Normalized path primitives of one page in display space.

``strokes`` are flattened one entry per path item: ``line`` carries two
endpoints, ``bezier`` carries all four control points (first and last are
on-curve), ``quad`` carries the four corners in perimeter order, ``rect``
carries four corners in perimeter order. ``total_primitives`` counts every item on
the page; ``matched`` counts the entries that survived the filters. Only
verified vector coordinates support calibrated measurements; coordinate
preflight and feature-association checks are still required.
