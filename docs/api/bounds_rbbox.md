# bounds_rbbox

## API Definition

```python
def bounds_rbbox(field: ScalarField) -> Tuple[Tuple[float, float, float], Tuple[float, float, float]]
```

*Source: field.py*

## Description

计算标量场的轴对齐包围盒。

## Parameters

### field

- **Description**: 标量场。

## Returns

Tuple[min_xyz, max_xyz]: 包围盒。
