# compare_model_to_inspection_rentityinspectionparity

## API Definition

```python
def compare_model_to_inspection_rentityinspectionparity(model: BRepModel, report: Mapping[str, Any], *, relative_tolerance: float = 1e-08, absolute_tolerance: float = 1e-08) -> EntityInspectionParity
```

*Source: inspect/brep/parity.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_model_to_inspection_rentityinspectionparity(...)`; unavailable inside GraphSession/@model

## Description

Check summary, geometry labels, measurements, and incidence parity.
