# InspectionSummaryComparison

## Class Definition

```python
class InspectionSummaryComparison(volume_delta: float, surface_area_delta: float, bounding_box_delta: tuple[float, ...], counts_equal: bool, surface_type_counts_equal: bool, edge_type_counts_equal: bool)
```

*Source: inspect/brep/compare.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.InspectionSummaryComparison(...)`; unavailable inside GraphSession/@model

## Description

Fast report-level diagnostics; not a geometric acceptance result.
