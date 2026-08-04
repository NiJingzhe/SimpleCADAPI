# compare_step_to_inspection_rentityinspectionparity

## API Definition

```python
def compare_step_to_inspection_rentityinspectionparity(step_path: str | Path, report_path: str | Path, *, relative_tolerance: float = 1e-08, absolute_tolerance: float = 1e-08) -> EntityInspectionParity
```

*Source: inspect/brep/parity.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_step_to_inspection_rentityinspectionparity(...)`; unavailable inside GraphSession/@model

## Description

Load a STEP file and compare it with a serialized BRepInspection report.
