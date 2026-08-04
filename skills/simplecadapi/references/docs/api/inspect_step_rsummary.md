# inspect_step_rsummary

## API Definition

```python
def inspect_step_rsummary(path: str | Path, *, include_parameter_groups: bool = False, max_parameter_groups: int = 24, examples_per_group: int = 3) -> dict[str, Any]
```

*Source: inspect/brep/model.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.inspect_step_rsummary(...)`; unavailable inside GraphSession/@model

## Description

Return global material and topology facts for one STEP file.
