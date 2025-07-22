# make_segment_redge

## API定义

```python
def make_segment_redge(start: Tuple[float, float, float], end: Tuple[float, float, float]) -> Edge
```

## API作用

与make_line_redge功能完全相同，提供更直观的函数名称。用于创建两点之间的
直线段，是构建复杂几何形状的基础元素。

## API参数说明

### start

- **类型**: `Tuple[float, float, float]`
- **说明**: 起始点坐标 (x, y, z)，定义线段的起点

### end

- **类型**: `Tuple[float, float, float]`
- **说明**: 结束点坐标 (x, y, z)，定义线段的终点

### 返回值

Edge: 创建的边对象，表示连接两点的直线段
