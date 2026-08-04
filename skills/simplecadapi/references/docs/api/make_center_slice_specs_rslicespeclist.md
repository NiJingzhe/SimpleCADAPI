# make_center_slice_specs_rslicespeclist

## API Definition

```python
def make_center_slice_specs_rslicespeclist(minimum: np.ndarray, maximum: np.ndarray) -> tuple[SliceSpec, ...]
```

*Source: inspect/brep/slices.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.make_center_slice_specs_rslicespeclist(...)`; unavailable inside GraphSession/@model

## Description

Return one center slice normal to each global axis.
