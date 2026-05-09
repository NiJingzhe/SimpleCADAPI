# bounds_rbbox

## API Definition

```python
def bounds_rbbox(field: ScalarField) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]
```

*Source: field.py*

## Description

Compute the axis-aligned bounding box of a scalar field.

## Parameters

### field

- **Description**: Scalar field.

## Returns

Tuple[min_xyz, max_xyz]: Bounding box.
