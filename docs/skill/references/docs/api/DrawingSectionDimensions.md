# DrawingSectionDimensions

## Class Definition

```python
class DrawingSectionDimensions(source: str, plane: dict[str, Any], closed_contour_count: int, open_contour_count: int, measurements: list[dict[str, Any]], metadata: dict[str, Any] = field(default_factory=dict), configuration: dict[str, Any] = field(default_factory=dict), section_validation: dict[str, Any] = field(default_factory=dict), circle_diagnostics: list[dict[str, Any]] = field(default_factory=list))
```

*Source: inspect/drawing/section.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.DrawingSectionDimensions(...)`; unavailable inside GraphSession

## Description

Candidate dimensions measured from one model section.

Entries are candidates, not verdicts: the caller picks the ones that
correspond to ledger rows and passes them back to
:func:`render_model_section_rpath` with ``dim_id`` / ``nominal`` filled
in. ``thickness`` candidates arise only from nested contour pairs; wall
thickness of side-by-side strips shows up as a contour ``extent``.
``section_validation`` separately reports closure, material topology and
solid/section/display point checks; ``circle_diagnostics`` includes open
contours and rejected fits. Neither output turns an uncertain value into
a verified dimension.
