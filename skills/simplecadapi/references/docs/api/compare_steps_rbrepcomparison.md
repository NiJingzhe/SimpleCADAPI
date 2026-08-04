# compare_steps_rbrepcomparison

## API Definition

```python
def compare_steps_rbrepcomparison(target_path: str | Path, candidate_path: str | Path, **kwargs) -> BRepComparison
```

*Source: inspect/brep/compare.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_steps_rbrepcomparison(...)`; unavailable inside GraphSession/@model

## Description

Load two STEP files and run the strict BREP comparison.
