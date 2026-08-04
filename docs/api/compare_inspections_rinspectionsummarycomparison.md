# compare_inspections_rinspectionsummarycomparison

## API Definition

```python
def compare_inspections_rinspectionsummarycomparison(target: BRepInspection, candidate: BRepInspection) -> InspectionSummaryComparison
```

*Source: inspect/brep/compare.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_inspections_rinspectionsummarycomparison(...)`; unavailable inside GraphSession/@model

## Description

Compare inexpensive inspection summaries without claiming BREP equality.
