# make_spline_rwire

## API Definition

```python
def make_spline_rwire(points: List[Tuple[float, float, float]], tangents: Optional[List[Tuple[float, float, float]]] = None, closed: bool = False) -> Wire
```

*Source: operations.py*

## Description

创建样条曲线并返回线对象

创建样条曲线线对象，与make_spline_redge功能相同但返回线对象。
可以设置为闭合样条曲线，适用于构建复杂的封闭轮廓。

## Parameters

### points

- **Type**: `List[Tuple[float, float, float]]`
- **Description**: 控制点坐标列表 [(x, y, z), ...]， 至少需要2个点，点的顺序决定样条曲线的走向

### tangents

- **Type**: `Optional[List[Tuple[float, float, float]]], optional`
- **Description**: 可选的切线向量列表 [(x, y, z), ...]，如果提供则数量必须与控制点一致

### closed

- **Type**: `bool, optional`
- **Description**: 是否创建闭合的样条曲线，默认为False

## Returns

Wire: 创建的线对象，包含一个样条曲线

## Raises

- **ValueError**: 当控制点少于2个或切线向量数量不匹配时抛出异常

## Examples

### Example 1
```python
# 创建开放样条曲线线
points = [(0, 0, 0), (2, 3, 0), (4, 1, 0), (6, 2, 0)]
spline_wire = make_spline_rwire(points)
```

### Example 2
```python
# 创建闭合样条曲线
points = [(0, 0, 0), (2, 2, 0), (4, 0, 0), (2, -2, 0)]
closed_spline = make_spline_rwire(points, closed=True)
```
