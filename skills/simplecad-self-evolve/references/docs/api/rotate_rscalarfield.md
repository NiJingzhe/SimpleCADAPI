# rotate_rscalarfield

## API Definition

```python
def rotate_rscalarfield(field: ScalarField, axis: Tuple[float, float, float], angle_degrees: float) -> ScalarField
```

*Source: field.py*

## Description

绕原点旋转标量场。

## Parameters

### field

- **Description**: 输入标量场。

### axis

- **Description**: 旋转轴向量 (x, y, z)。

### angle_degrees

- **Description**: 旋转角度（度）。

## Returns

ScalarField: 旋转后的标量场。
