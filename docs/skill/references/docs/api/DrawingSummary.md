# DrawingSummary

## Class Definition

```python
class DrawingSummary(source: str, page_count: int, route: str, metadata: dict[str, Any], fonts: list[str], pages: list[dict[str, Any]])
```

*Source: inspect/drawing/summary.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.DrawingSummary(...)`; unavailable inside GraphSession

## Description

Facts-only health report for one PDF drawing document.

``route`` recommends how the downstream analysis should treat the file:
``vector`` (mine the text and vector layers), ``raster`` (render-only
reading), ``mixed`` (both layers present), ``text_only`` (no graphics at
all), or ``empty`` (nothing extractable). The verdict is counted from
per-page facts; no geometric or semantic interpretation happens here.
