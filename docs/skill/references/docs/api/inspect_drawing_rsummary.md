# inspect_drawing_rsummary

## API Definition

```python
def inspect_drawing_rsummary(path: str | Path) -> DrawingSummary
```

*Source: inspect/drawing/summary.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.inspect_drawing_rsummary(...)`; unavailable inside GraphSession

## Description

Summarize one PDF drawing document and recommend an analysis route.

Collects per-page facts only: display-space size and stored rotation,
text object counts, vector path/primitive counts with kind and color
census, embedded image counts, document metadata, and font names. The
``route`` verdict decides whether the drawing can be mined as vector
evidence or only read through rendered views; a ``mixed`` or ``raster``
verdict means measured claims are not available from the file alone.
