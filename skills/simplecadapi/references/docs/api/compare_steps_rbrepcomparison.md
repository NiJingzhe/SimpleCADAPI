# compare_steps_rbrepcomparison

## API Definition

```python
def compare_steps_rbrepcomparison(target_path: str | Path, candidate_path: str | Path, **kwargs) -> BRepComparison
```

*Source: inspect/brep/compare.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.compare_steps_rbrepcomparison(...)`; unavailable inside GraphSession/@model

## Description

Load two STEP files and run the strict BREP comparison. The returned
`BRepComparison` includes diagnostics for validity, bounds, material,
topology, and carrier types. Call `to_error_summary()` to report every failed
check by plausible common root cause, or `write_error_summary_json(...)` to
persist that report. The strict hard gate is unchanged.
