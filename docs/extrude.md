# extrude

## 定义
```python
def extrude(sketch: Sketch, distance: Optional[float] = None) -> Body
```

## 描述

将2D草图沿其法向方向拉伸指定距离，创建3D实体。这是最基础的3D建模操作之一。

### 参数
- `sketch` (Sketch): 要拉伸的2D草图
- `distance` (Optional[float]): 拉伸距离，必须指定

### 返回值
- `Body`: 拉伸后的3D实体

### 特点
- 草图必须是闭合的平面轮廓
- 拉伸方向垂直于草图平面
- 距离必须为正值
- 结果是一个实体Body对象

## 示例

### 基础形状拉伸
```python
from simplecadapi import *

# 矩形拉伸
rect = make_rectangle(2.0, 1.0, center=True)
extruded_rect = extrude(rect, distance=0.5)

# 圆形拉伸成圆柱
circle = make_circle(0.5)
extruded_circle = extrude(circle, distance=1.0)
```

### 复杂轮廓拉伸
```python
from simplecadapi import *

# 创建L型轮廓并拉伸
p1 = make_point(0, 0, 0)
p2 = make_point(2, 0, 0)
p3 = make_point(2, 1, 0)
p4 = make_point(1, 1, 0)
p5 = make_point(1, 2, 0)
p6 = make_point(0, 2, 0)

l_lines = [
    make_segment(p1, p2),
    make_segment(p2, p3),
    make_segment(p3, p4),
    make_segment(p4, p5),
    make_segment(p5, p6),
    make_segment(p6, p1)
]

l_sketch = make_sketch(l_lines)
l_shape = extrude(l_sketch, distance=0.5)
```

### 不同坐标系中拉伸
```python
from simplecadapi import *

# 在倾斜坐标系中拉伸
with LocalCoordinateSystem(
    origin=(2, 2, 1),
    x_axis=(1, 0, 0),
    y_axis=(0, 0.707, 0.707)  # 45度倾斜
):
    tilted_rect = make_rectangle(1.5, 1.0, center=True)
    tilted_solid = extrude(tilted_rect, distance=0.8)
    # 拉伸方向会沿着倾斜坐标系的Z轴
```
- 拉伸方向沿着草图所在平面的法向量
- distance必须为正值
- 草图必须是闭合的才能进行拉伸
- 拉伸是最常用的3D建模操作，适用于大多数规则形状
- 结果Body对象可以进行进一步的布尔运算、圆角、倒角等操作
- 如果草图在XY平面，拉伸方向为+Z方向
