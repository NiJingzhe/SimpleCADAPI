# smooth_subtract_rscalarfield

## API Definition

```python
def smooth_subtract_rscalarfield(a: ScalarField, b: ScalarField, k: float) -> ScalarField
```

*Source: field.py*

## Description

平滑差集组合标量场。

## Parameters

### a

- **Description**: 被减标量场。

### b

- **Description**: 减去标量场。

### k

- **Description**: 平滑系数，必须为正。

## Returns

ScalarField: 平滑差集标量场。
