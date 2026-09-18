# extract_drawing_primitives_rstrokes

## API Definition

```python
def extract_drawing_primitives_rstrokes(path: str | Path, page: int = 0, *, rect: Sequence[float] | None = None, color: str | Sequence[float] | None = None, fill: str | Sequence[float] | None = None, kinds: Sequence[str] | None = None) -> DrawingStrokes
```

*Source: inspect/drawing/geometry.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.extract_drawing_primitives_rstrokes(...)`; unavailable inside GraphSession

## Description

Extract the vector primitives of one page in display-space coordinates.

Vector coordinates are measurement evidence after coordinate preflight
and feature-association checks. All coordinates are
mapped through the page rotation matrix, so distances measured here are
directly comparable with annotation anchors and rendered views. Filter
per view with ``rect`` (display-space ``[x0, y0, x1, y1]``) — large
drawings carry tens of thousands of primitives and unfiltered dumps are
unusable. ``color`` matches the stroke color, ``fill`` the fill color
(either as ``"#rrggbb"`` or 0-1 RGB floats); run with no filters first
and read the color census to discover what exists (hatch fills, axis
lines) before narrowing. Color semantics are per-drawing conventions:
the census reports facts, assigning meaning ("this red line is a hole
axis") is the caller's job. ``kinds`` selects among ``line``, ``bezier``,
``quad``, ``rect``.
Rectangles now carry four perimeter corners (result version 2.0). Region
filtering is inclusive bounding-box overlap, not exact curve clipping;
Bezier boxes bound control points. IDs refer to unfiltered page item order.
Metadata includes SHA-256, page/rotation/MediaBox/CropBox, pt units and version.
