# validate_section_annotations_rreport

## API Definition

```python
def validate_section_annotations_rreport(model: Any, plane: Mapping[str, Sequence[float]], dimensions: Sequence[Mapping[str, Any]], ledger: Sequence[Mapping[str, Any]], *, anchor_tolerance_mm: float = 1e-05) -> dict[str, Any]
```

*Source: inspect/drawing/evidence.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.validate_section_annotations_rreport(...)`; unavailable inside GraphSession

## Description

Remeasure current BREP and reject forged values, targets, IDs and stale evidence.

The independent rerun uses the recorded algorithm configuration, comparing
unrounded values exactly. Anchors must lie on selected continuous geometry
within anchor_tolerance_mm (association check only, not dimensional accuracy).
The ledger's measurement_contract separately binds kind, direction, definition
and line point, as well as units/coordinate space. Its feature mapping and
the actual rounding error/display step are checked independently of the number.
The ledger is the separately reviewed feature mapping; caller-supplied raw
annotation metadata is never its own source of truth. Layout review is separate.
