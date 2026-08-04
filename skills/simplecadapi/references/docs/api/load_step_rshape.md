# load_step_rshape

## API Definition

```python
def load_step_rshape(path: str | Path, *, require_single_root: bool = True, require_valid: bool = True) -> TopoDS_Shape
```

*Source: inspect/brep/io.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.load_step_rshape(...)`; unavailable inside GraphSession/@model

## Description

Load one transferred STEP shape and optionally require a valid BREP.
