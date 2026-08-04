# load_step_rbrepmodel

## API Definition

```python
def load_step_rbrepmodel(path: str | Path) -> BRepModel
```

*Source: inspect/brep/model.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.load_step_rbrepmodel(...)`; unavailable inside GraphSession/@model

## Description

Load and cache a STEP model with deterministic topology ids.
