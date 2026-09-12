# extract_drawing_text_rwords

## API Definition

```python
def extract_drawing_text_rwords(path: str | Path, page: int = 0, *, cluster_gap_pt: float = 2.5) -> DrawingText
```

*Source: inspect/drawing/text.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.extract_drawing_text_rwords(...)`; unavailable inside GraphSession

## Description

Extract every text object of one page in display-space coordinates.

Word boxes are mapped through the page rotation matrix, so they line up
with rendered views and with :func:`extract_drawing_primitives_rstrokes`
output after coordinate preflight. ``cluster_gap_pt`` controls proximity
combination candidates; it cannot confirm tolerance stacks or feature
assignment. Pass ``cluster_gap_pt=0`` for bare words. Metadata includes source
hash/page/rotation/MediaBox/CropBox/space/units/result version. Each word keeps
its original object and display-space direction vector.
The text layer is the complete "what exists on the sheet" inventory, but
reading order is not visual order: never read dimensions from this layer
alone, confirm attachment on a rendered view.
