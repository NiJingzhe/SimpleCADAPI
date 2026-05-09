# smooth_subtract_rscalarfield

## API Definition

```python
def smooth_subtract_rscalarfield(a: ScalarField, b: ScalarField, k: float) -> ScalarField
```

*Source: field.py*

## Description

Create a smooth subtraction scalar field.

## Parameters

### a

- **Description**: Minuend scalar field.

### b

- **Description**: Subtrahend scalar field.

### k

- **Description**: Smoothing factor, which must be positive.

## Returns

ScalarField: Smooth subtraction scalar field.
