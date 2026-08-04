# measure_shape_mass_rtuple

## API Definition

```python
def measure_shape_mass_rtuple(shape: TopoDS_Shape, kind: PropertyKind) -> tuple[float, np.ndarray]
```

*Source: inspect/brep/io.py*

## Import Surface

- inspection namespace: `from simplecadapi.inspect import brep` then `brep.measure_shape_mass_rtuple(...)`; unavailable inside GraphSession/@model

## Description

Return mass-like value and center for volume, area, or length.
