# make_angle_arc_redge

## API定义

```python
def make_angle_arc_redge(center: Tuple[float, float, float], radius: float, start_angle: float, end_angle: float, normal: Tuple[float, float, float] = (0, 0, 1)) -> Edge
```

*来源文件: operations.py*

## API作用

通过指定中心点、半径和角度范围创建圆弧边。角度采用度数制，
0度对应X轴正方向，逆时针为正角度。可以创建任意角度范围的圆弧。

## API参数说明

### center

- **类型**: `Tuple[float, float, float]`
- **说明**: 圆弧的中心点坐标 (x, y, z)

### radius

- **类型**: `float`
- **说明**: 圆弧的半径，必须为正数

### start_angle

- **类型**: `float`
- **说明**: 起始角度，单位为度数（0-360）

### end_angle

- **类型**: `float`
- **说明**: 结束角度，单位为度数（0-360）

### normal

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 圆弧所在平面的法向量 (x, y, z)， 默认为 (0, 0, 1) 表示XY平面

## 返回值说明

Edge: 创建的边对象，表示指定角度范围的圆弧

## 异常

- **ValueError**: 当半径小于等于0或其他参数无效时抛出异常

## API使用例子

```python
# 创建90度圆弧（从0度到90度）
arc_90 = make_angle_arc_redge((0, 0, 0), 2.0, 0, 90)
# 创建180度半圆弧
semicircle = make_angle_arc_redge((0, 0, 0), 1.5, 0, 180)
# 创建270度圆弧
arc_270 = make_angle_arc_redge((0, 0, 0), 1.0, 45, 315)
# 创建垂直平面上的圆弧
vertical_arc = make_angle_arc_redge((0, 0, 0), 1.0, 0, 90, (1, 0, 0))
```
