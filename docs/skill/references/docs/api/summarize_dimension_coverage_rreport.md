# summarize_dimension_coverage_rreport

## API Definition

```python
def summarize_dimension_coverage_rreport(verdicts: Sequence[Mapping[str, Any]], *, expected_dim_ids: Sequence[str]) -> dict[str, Any]
```

*Source: inspect/drawing/evidence.py*

## Import Surface

- drawing-inspection namespace: `from simplecadapi.inspect import drawing` then `drawing.summarize_dimension_coverage_rreport(...)`; unavailable inside GraphSession

## Description

Count value, association and layout against every expected ledger DIM ID.

Missing verdict rows count as unverified in all columns. Duplicate or
unexpected IDs raise, so coverage cannot hide omitted ledger entries.
