# inspect_drawing_coordinates_rreport

## API Definition

```python
def inspect_drawing_coordinates_rreport(path: str | Path, page: int = 0, *, observations: Sequence[Mapping[str, Any]] = (), dpi: int = 150, rect: Sequence[float] | None = None, tolerance_px: float = 2.0, out_dir: str | Path = '.', stem: str = 'coordinate_preflight') -> dict[str, Any]
```

*Source: inspect/drawing/preflight.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.inspect_drawing_coordinates_rreport(...)`; unavailable inside GraphSession

## Description

Check text and vector landmarks against independently observed image pixels.

Writes a viewport and a preflight report with source/page/box/rotation facts.
Each observation has kind (text/vector), object_id, point_index, pixel [x,y],
source_id, page, dpi, rect_display, and evidence (review/crop reference).
Text points are bbox corners TL,TR,BR,BL; vector points are extracted vertices
or Bezier controls. Bezier controls need independently derived references,
since they need not be on the rendered curve. Pixels use top-left pixel-edge
coordinates of this exact viewport. Missing text/vector observations remain
pending: inverse-transform consistency alone never proves visual alignment.
