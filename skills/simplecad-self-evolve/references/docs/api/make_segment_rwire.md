# make_segment_rwire

## API Definition

```python
def make_segment_rwire(start: Tuple[float, float, float], end: Tuple[float, float, float]) -> Wire
```

*Source: operations.py*

## Description

创建线段并返回线对象

创建包含单个线段的线对象，用于构建更复杂的线框结构。与make_segment_redge
不同，此函数返回的是线对象，可以与其他线对象连接形成复杂路径。

## Parameters

### start

- **Type**: `Tuple[float, float, float]`
- **Description**: 起始点坐标 (x, y, z)，定义线段的起点

### end

- **Type**: `Tuple[float, float, float]`
- **Description**: 结束点坐标 (x, y, z)，定义线段的终点

## Returns

Wire: 创建的线对象，包含一个连接两点的直线段

## Raises

- **ValueError**: 当坐标无效或创建线对象失败时抛出异常

## Examples

### Example 1
```python
# 创建基本线段线
wire = make_segment_rwire((0, 0, 0), (3, 0, 0))
```

### Example 2
```python
# 创建斜线段
diagonal_wire = make_segment_rwire((0, 0, 0), (2, 2, 0))
```
