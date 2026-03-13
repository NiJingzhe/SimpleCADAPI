# make_segment_redge

## API Definition

```python
def make_segment_redge(start: Tuple[float, float, float], end: Tuple[float, float, float]) -> Edge
```

*Source: operations.py*

## Description

创建线段并返回边对象（make_line_redge的别名函数）

与make_line_redge功能完全相同，提供更直观的函数名称。用于创建两点之间的
直线段，是构建复杂几何形状的基础元素。

## Parameters

### start

- **Type**: `Tuple[float, float, float]`
- **Description**: 起始点坐标 (x, y, z)，定义线段的起点

### end

- **Type**: `Tuple[float, float, float]`
- **Description**: 结束点坐标 (x, y, z)，定义线段的终点

## Returns

Edge: 创建的边对象，表示连接两点的直线段

## Examples

### Example 1
```python
# 创建垂直线段
vertical_line = make_segment_redge((0, 0, 0), (0, 0, 5))
```

### Example 2
```python
# 创建对角线段
diagonal = make_segment_redge((0, 0, 0), (1, 1, 1))
```
