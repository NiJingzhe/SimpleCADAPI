# make_circle_redge

## API定义

```python
def make_circle_redge(center: Tuple[float, float, float], radius: float, normal: Tuple[float, float, float] = (0, 0, 1)) -> Edge
```

*来源文件: operations.py*

## API作用

创建圆形边对象，用于构建圆形轮廓、圆弧路径等。圆的方向由法向量确定，
支持在任意平面内创建圆形。支持当前坐标系变换。

## API参数说明

### center

- **类型**: `Tuple[float, float, float]`
- **说明**: 圆心坐标 (x, y, z)，定义圆的中心位置

### radius

- **类型**: `float`
- **说明**: 圆的半径，必须为正数

### normal

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 圆所在平面的法向量 (x, y, z)， 默认为 (0, 0, 1) 表示XY平面

## 返回值说明

Edge: 创建的边对象，表示一个完整的圆形

## 异常

- **ValueError**: 当半径小于等于0或其他参数无效时抛出异常

## API使用例子

```python
# 创建XY平面上的圆
circle = make_circle_redge((0, 0, 0), 2.0)
# 创建垂直平面上的圆
vertical_circle = make_circle_redge((0, 0, 0), 1.5, (1, 0, 0))
# 创建指定位置的圆
offset_circle = make_circle_redge((2, 3, 1), 1.0, (0, 0, 1))
```
