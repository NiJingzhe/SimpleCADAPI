# make_angle_arc_rwire

## API定义

```python
def make_angle_arc_rwire(center: Tuple[float, float, float], radius: float, start_angle: float, end_angle: float, normal: Tuple[float, float, float] = (0, 0, 1)) -> Wire
```

*来源文件: operations.py*

## API作用

通过指定中心点、半径和角度范围创建圆弧线。
角度采用度数制，0度对应X轴正方向，逆时针为正角度。
可以创建任意角度范围的圆弧线。

## API参数说明

### center

- **说明**: 圆心坐标

### radius

- **说明**: 半径

### start_angle

- **说明**: 起始角度（弧度）

### end_angle

- **说明**: 结束角度（弧度）

### normal

- **说明**: 法向量

## 返回值说明

Wire: 线对象，表示通过角度创建的圆弧线

## 异常

- **ValueError**: 当半径小于等于0或其他参数无效时

## API使用例子

```python
# 创建90度圆弧线（从0度到90度）
arc_90_wire = make_angle_arc_rwire((0, 0, 0), 2.0, 0, 90)
# 创建180度半圆弧线
semicircle_wire = make_angle_arc_rwire((0, 0, 0), 1.5, 0, 180)
# 创建270度圆弧线
arc_270_wire = make_angle_arc_rwire((0, 0, 0), 1.0, 45, 315)
# 创建垂直平面（YZ，法相指向X轴正方向）上的圆弧线
vertical_arc_wire = make_angle_arc_rwire((0, 0, 0), 1.0, 0, 90, (1, 0, 0))
```
