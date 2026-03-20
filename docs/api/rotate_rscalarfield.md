# rotate_rscalarfield

## API Definition

```python
def rotate_rscalarfield(field: ScalarField, axis: Tuple[float, float, float], angle_degrees: float) -> ScalarField
```

*Source: field.py*

## Description

Rotate a scalar field around the origin.

## Parameters

### field

- **Description**: Input scalar field.

### axis

- **Description**: Rotation axis vector `(x, y, z)`.

### angle_degrees

- **Description**: Rotation angle in degrees.

## Returns

ScalarField: Rotated scalar field.
