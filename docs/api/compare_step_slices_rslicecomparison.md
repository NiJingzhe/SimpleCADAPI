# compare_step_slices_rslicecomparison

## API Definition

```python
def compare_step_slices_rslicecomparison(target_path: str | Path, candidate_path: str | Path, **kwargs) -> SliceComparison
```

*Source: inspect/brep/slices.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_step_slices_rslicecomparison(...)`; unavailable inside GraphSession/@model

## Description

Load two STEP solids and compare physical occupancy slices.
