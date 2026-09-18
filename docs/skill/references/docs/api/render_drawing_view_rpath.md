# render_drawing_view_rpath

## API Definition

```python
def render_drawing_view_rpath(path: str | Path, page: int = 0, *, rect: Sequence[float] | None = None, anchor: Mapping[str, Any] | None = None, pad_fraction: float = _DEFAULT_PAD_FRACTION, dpi: int = 300, out_dir: str | Path = '.', stem: str | None = None) -> Path
```

*Source: inspect/drawing/render.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.render_drawing_view_rpath(...)`; unavailable inside GraphSession

## Description

Render one page (or one region of it) to PNG for visual judgment.

Pass neither ``rect`` nor ``anchor`` for a full-page overview; pass
``rect`` (display-space ``[x0, y0, x1, y1]``, the same coordinates the
other drawing-inspection functions report) for a region crop; or pass an
``anchor`` (a word or cluster dict from ``extract_drawing_text_rwords``)
to frame that annotation with ``pad_fraction`` margin so its leader lines
stay attached. A ``<png>.json`` sidecar records the source file, page,
display-space rect, and dpi so every viewed pixel is traceable back to
sheet coordinates. Visual reading through this viewport is evidence for
annotation attachment and small print, never for precise numbers: those
come from the vector layer.
The sidecar distinguishes requested and effective crop rectangles and records
the integer pixmap origin, page-to-pixel and inverse homogeneous matrices.
Page units are pt; pixel units are px, using pixel-edge coordinates. Source
hash, page boxes, rotation, coordinate space and result version are included.
