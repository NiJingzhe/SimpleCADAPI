# CoordinateSystem

`CoordinateSystem` represents a right-handed local coordinate frame used by `SimpleWorkplane` and public modeling operations.

## Public constructor

```python
CoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(1, 0, 0),
    y_axis=(0, 1, 0),
    z_axis=(0, 0, 1),
)
```

## Main capabilities

- Store an origin and orthonormal axes.
- Transform local points to global coordinates.
- Transform local vectors to global vectors.
- Format readable frame diagnostics.

## Example

```python
import simplecadapi as scad

cs = scad.CoordinateSystem(origin=(10, 0, 0))
print(cs.transform_point((1, 2, 3)))
```
