# extrude 函数文档

## 定义
```python
def extrude(sketch: Sketch, distance: Optional[float] = None) -> Body
```

## 作用
将2D草图沿其法向方向拉伸指定距离，创建3D实体。这是最基础的3D建模操作之一。

## 参数
- `sketch` (Sketch): 要拉伸的2D草图
- `distance` (Optional[float]): 拉伸距离，必须指定

## 返回值
- `Body`: 拉伸后的3D实体

## 示例代码

### 基础矩形拉伸（来自comprehensive_test）
```python
from simplecadapi import *

# 创建矩形并拉伸
rect = make_rectangle(2.0, 1.0, center=True)
extruded_rect = extrude(rect, distance=0.5)
```

### 圆形拉伸成圆柱
```python
from simplecadapi import *

# 创建圆形并拉伸
circle = make_circle(0.5)
extruded_circle = extrude(circle, distance=1.0)
# 结果是一个高度为1.0，半径为0.5的圆柱体
```

### 复杂形状拉伸
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
    make_segement(p1, p2),
    make_segement(p2, p3),
    make_segement(p3, p4),
    make_segement(p4, p5),
    make_segement(p5, p6),
    make_segement(p6, p1)
]

l_sketch = make_sketch(l_lines)
l_shape = extrude(l_sketch, distance=0.5)
```

### 三角形拉伸
```python
from simplecadapi import *

# 创建三角形并拉伸成三角柱
triangle = make_triangle(
    make_point(0, 0, 0),
    make_point(2, 0, 0),
    make_point(1, 1.732, 0)  # 等边三角形
)

triangular_prism = extrude(triangle, distance=1.5)
```

### 椭圆拉伸
```python
from simplecadapi import *

# 创建椭圆并拉伸成椭圆柱
center = make_point(0, 0, 0)
ellipse = make_ellipse(center, major_axis=3.0, minor_axis=1.5)
elliptical_cylinder = extrude(ellipse, distance=2.0)
```

### 在不同坐标系中拉伸
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

### 用于后续布尔运算
```python
from simplecadapi import *

# 创建两个拉伸体进行布尔运算
rect1 = make_rectangle(3.0, 3.0, center=True)
box1 = extrude(rect1, distance=1.0)

# 在稍微偏移的位置创建第二个
with LocalCoordinateSystem(origin=(1, 1, 0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    rect2 = make_rectangle(2.0, 2.0, center=True)
    box2 = extrude(rect2, distance=1.0)

# 布尔运算
union_result = union(box1, box2)
intersection_result = intersect(box1, box2)
```

### 薄壁结构拉伸
```python
from simplecadapi import *

# 创建薄壁矩形框架
outer_rect = make_rectangle(4.0, 3.0, center=True)
outer_box = extrude(outer_rect, distance=0.2)

inner_rect = make_rectangle(3.6, 2.6, center=True)
inner_box = extrude(inner_rect, distance=0.3)  # 稍高确保完全切穿

frame = cut(outer_box, inner_box)
```

### 分层拉伸（多个高度）
```python
from simplecadapi import *

# 创建分层结构
base_rect = make_rectangle(3.0, 3.0, center=True)
base_layer = extrude(base_rect, distance=0.3)

with LocalCoordinateSystem(origin=(0, 0, 0.3), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    mid_rect = make_rectangle(2.0, 2.0, center=True)
    mid_layer = extrude(mid_rect, distance=0.3)

with LocalCoordinateSystem(origin=(0, 0, 0.6), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    top_rect = make_rectangle(1.0, 1.0, center=True)
    top_layer = extrude(top_rect, distance=0.3)

# 合并各层
combined = union(base_layer, mid_layer)
pyramid = union(combined, top_layer)
```

## 注意事项
- 拉伸方向沿着草图所在平面的法向量
- distance必须为正值
- 草图必须是闭合的才能进行拉伸
- 拉伸是最常用的3D建模操作，适用于大多数规则形状
- 结果Body对象可以进行进一步的布尔运算、圆角、倒角等操作
- 如果草图在XY平面，拉伸方向为+Z方向
