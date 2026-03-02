# make_three_point_arc_redge

## API定义

```python
def make_three_point_arc_redge(start: Tuple[float, float, float], middle: Tuple[float, float, float], end: Tuple[float, float, float]) -> Edge
```

*来源文件: operations.py*

## API作用

通过三个点创建圆弧边，三个点不能共线。圆弧从起始点经过中间点到结束点。
中间点的位置决定了圆弧的弯曲程度和方向。

## API参数说明

### start

- **类型**: `Tuple[float, float, float]`
- **说明**: 圆弧的起始点坐标 (x, y, z)

### middle

- **类型**: `Tuple[float, float, float]`
- **说明**: 圆弧上的中间点坐标 (x, y, z)， 用于确定圆弧的曲率和方向

### end

- **类型**: `Tuple[float, float, float]`
- **说明**: 圆弧的结束点坐标 (x, y, z)

## 返回值说明

Edge: 创建的边对象，表示通过三点的圆弧

## 异常

- **ValueError**: 当三个点共线或坐标无效时抛出异常

## API使用例子

```python
# 创建90度圆弧
arc = make_three_point_arc_redge((0, 0, 0), (1, 1, 0), (2, 0, 0))
# 创建大圆弧
large_arc = make_three_point_arc_redge((0, 0, 0), (0, 3, 0), (0, 6, 0))
# 创建3D圆弧
arc_3d = make_three_point_arc_redge((0, 0, 0), (1, 1, 1), (2, 0, 2))
```
