# inspect_step_components_rdescriptorlist

## API Definition

```python
def inspect_step_components_rdescriptorlist(step_path: str | Path) -> list[dict[str, object]]
```

*Source: inspect/brep/render.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.inspect_step_components_rdescriptorlist(...)`; unavailable inside GraphSession/@model

## Description

List targetable XCAF component occurrences with unique hierarchy paths.
