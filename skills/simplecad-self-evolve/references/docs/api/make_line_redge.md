# make_line_redge

## API Definition

```python
def make_line_redge(start: Tuple[float, float, float], end: Tuple[float, float, float]) -> Edge
```

*Source: operations.py*

## Description

创建两点之间的直线段并返回边对象

创建两点之间的直线段，是构建复杂几何形状的基础元素。可用于构造线框、
创建草图轮廓、定义路径等。支持当前坐标系变换。

## Parameters

### start

- **Type**: `Tuple[float, float, float]`
- **Description**: 起始点坐标 (x, y, z)，定义线段的起点

### end

- **Type**: `Tuple[float, float, float]`
- **Description**: 结束点坐标 (x, y, z)，定义线段的终点

## Returns

Edge: 创建的边对象，表示连接两点的直线段

## Raises

- **ValueError**: 当坐标无效或起始点与结束点重合时抛出异常

## Examples

### Example 1
```python
# 创建水平线段
line = make_line_redge((0, 0, 0), (5, 0, 0))
```

### Example 2
```python
# 创建三维空间中的线段
line_3d = make_line_redge((1, 1, 1), (3, 2, 4))
```

### Example 3
```python
 # 在工作平面中创建线段
 with SimpleWorkplane((0, 0, 1)):
...     elevated_line = make_line_redge((0, 0, 0), (2, 2, 0))
```
