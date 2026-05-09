# make_field_surface_rsolid

## API Definition

```python
def make_field_surface_rsolid(field, bounds: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = None, resolution: Tuple[int, int, int] = (24, 24, 24), iso: float = 0.0, cap_bounds: bool = True) -> Solid
```

*Source: operations.py*

## Description

Build a closed solid from a scalar field isosurface.
