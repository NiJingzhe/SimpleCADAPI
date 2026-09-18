# DrawingText

## Class Definition

```python
class DrawingText(source: str, page: int, rotation: int, width_pt: float, height_pt: float, words: list[dict[str, Any]], clusters: list[dict[str, Any]], metadata: dict[str, Any] = field(default_factory=dict))
```

*Source: inspect/drawing/text.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.DrawingText(...)`; unavailable inside GraphSession

## Description

All text objects of one page plus proximity clusters.

Word and cluster boxes are in display space (matching ``page.rect`` and
the image after the explicit pt-to-px transform). Clusters are proximity
combination candidates, not verified tolerance stacks or feature mappings.
Original word objects and display-space directions are preserved. Metadata
supplies source hash, zero-based page, rotation, page boxes, units and version.
