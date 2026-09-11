# build_section_annotation_rrecord

## API Definition

```python
def build_section_annotation_rrecord(measurement: Mapping[str, Any], ledger: Mapping[str, Any], *, error_assessment: Mapping[str, Any] | None = None, anchor: Sequence[float] | None = None, display_decimals: int | None = None) -> dict[str, Any]
```

*Source: inspect/drawing/evidence.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.build_section_annotation_rrecord(...)`; unavailable inside GraphSession

## Description

Build a bound annotation from a verified DIM and measurement record.

Pass a continuous measurement with its total error assessment and the
verified ledger schema of assess_dimension_rverdict. ``anchor`` is a local
section point on the selected target geometry. Without it the renderer
uses a placeholder and formal association validation cannot pass.
Display decimals default to one guard digit beyond tolerance-band width.
The formatter's step must not exceed band width, rounding error must not
exceed half its width, and the displayed number must remain in the band.
A zero-width band requires exact decimal representation. Insufficient
precision raises even for an explicit display_decimals override.
Independent validation against the current model is still required.
A measurement whose section_validation is missing, pending or failed cannot
produce a verified annotation, even if its numerical value fits tolerance.
