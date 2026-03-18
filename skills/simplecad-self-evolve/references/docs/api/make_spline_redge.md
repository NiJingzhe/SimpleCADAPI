# make_spline_redge

## API Definition

```python
def make_spline_redge(points: List[Tuple[float, float, float]], tangents: Optional[List[Tuple[float, float, float]]] = None) -> Edge
```

*Source: operations.py*

## Description

创建样条曲线并返回边对象

创建平滑的样条曲线边，用于构建复杂的曲线路径。样条曲线会平滑地通过
所有控制点，可选择性地指定每个点的切线方向来控制曲线的形状。

## Parameters

### points

- **Type**: `List[Tuple[float, float, float]]`
- **Description**: 控制点坐标列表 [(x, y, z), ...]， 至少需要2个点，点的顺序决定样条曲线的走向

### tangents

- **Type**: `Optional[List[Tuple[float, float, float]]], optional`
- **Description**: 可选的切线向量列表 [(x, y, z), ...]，如果提供则数量必须与控制点一致

## Returns

Edge: 创建的边对象，表示通过控制点的平滑样条曲线

## Raises

- **ValueError**: 当控制点少于2个或切线向量数量不匹配时抛出异常

## Examples

### Example 1
```python
# 创建简单的样条曲线
points = [(0, 0, 0), (1, 2, 0), (3, 1, 0), (4, 3, 0)]
spline = make_spline_redge(points)
```

### Example 2
```python
# 创建带切线控制的样条曲线
points = [(0, 0, 0), (2, 0, 0), (4, 0, 0)]
tangents = [(1, 0, 0), (0, 1, 0), (1, 0, 0)]
controlled_spline = make_spline_redge(points, tangents)
```

### Example 3
```python
# 创建3D样条曲线
points_3d = [(0, 0, 0), (1, 1, 1), (2, 0, 2), (3, 1, 1)]
spline_3d = make_spline_redge(points_3d)
```
