# scale_rscalarfield

## API Definition

```python
def scale_rscalarfield(field: ScalarField, factors: Tuple[float, float, float]) -> ScalarField
```

*Source: field.py*

## Description

缩放标量场（以原点为中心）。

## Parameters

### field

- **Description**: 输入标量场。

### factors

- **Description**: 缩放系数 (sx, sy, sz)。

## Returns

ScalarField: 缩放后的标量场。
