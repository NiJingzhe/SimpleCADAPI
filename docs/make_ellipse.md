# make_ellipse 函数文档

## 定义
```python
def make_ellipse(center: Point, major_axis: float, minor_axis: float, rotation: float = 0) -> Sketch
```

## 作用
创建椭圆形草图。使用多边形（32边形）近似椭圆，可以指定长轴、短轴和旋转角度。

## 参数
- `center` (Point): 椭圆的中心点
- `major_axis` (float): 长轴长度
- `minor_axis` (float): 短轴长度
- `rotation` (float): 旋转角度（弧度），默认为0

## 返回值
- `Sketch`: 椭圆形草图对象

## 示例代码

### 基础椭圆
```python
from simplecadapi import *

# 在原点创建椭圆
center = make_point(0, 0, 0)
ellipse = make_ellipse(center, major_axis=3.0, minor_axis=2.0)
```

### 旋转椭圆
```python
from simplecadapi import *
import math

# 创建45度旋转的椭圆
center = make_point(1, 1, 0)
rotated_ellipse = make_ellipse(
    center=center,
    major_axis=4.0,
    minor_axis=2.0,
    rotation=math.pi/4  # 45度
)
```

### 椭圆拉伸
```python
from simplecadapi import *

# 创建椭圆并拉伸成椭圆柱
center = make_point(0, 0, 0)
ellipse_sketch = make_ellipse(center, major_axis=2.0, minor_axis=1.0)
elliptical_cylinder = extrude(ellipse_sketch, distance=1.5)
```

### 近似圆形（特殊椭圆）
```python
from simplecadapi import *

# 当长轴等于短轴时，椭圆退化为圆形
center = make_point(2, 2, 0)
circle_like = make_ellipse(center, major_axis=2.0, minor_axis=2.0)
```

### 扁平椭圆
```python
from simplecadapi import *

# 创建非常扁的椭圆
center = make_point(0, 0, 0)
flat_ellipse = make_ellipse(
    center=center,
    major_axis=5.0,
    minor_axis=0.5
)

flat_disc = extrude(flat_ellipse, distance=0.1)
```

### 椭圆在不同坐标系中
```python
from simplecadapi import *

# 在局部坐标系中创建椭圆
with LocalCoordinateSystem(
    origin=(3, 3, 1),
    x_axis=(0.707, 0.707, 0),  # 45度旋转的坐标系
    y_axis=(-0.707, 0.707, 0)
):
    local_center = make_point(0, 0, 0)
    local_ellipse = make_ellipse(local_center, major_axis=2.0, minor_axis=1.2)
```

### 椭圆用于放样
```python
from simplecadapi import *

# 椭圆到矩形的放样
ellipse_base = make_ellipse(
    make_point(0, 0, 0),
    major_axis=3.0,
    minor_axis=1.5
)

with LocalCoordinateSystem(origin=(0, 0, 2), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    rect_top = make_rectangle(2.0, 2.0, center=True)

morphed_shape = loft([ellipse_base, rect_top])
```

### 不同旋转角度的椭圆系列
```python
from simplecadapi import *
import math

# 创建不同旋转角度的椭圆序列
ellipses = []
center = make_point(0, 0, 0)

for i in range(4):
    rotation = i * math.pi / 4  # 每次旋转45度
    ellipse = make_ellipse(
        center=center,
        major_axis=2.0,
        minor_axis=1.0,
        rotation=rotation
    )
    ellipses.append(ellipse)
```

### 椭圆扫掠
```python
from simplecadapi import *

# 椭圆截面的扫掠
ellipse_profile = make_ellipse(
    make_point(0, 0, 0),
    major_axis=0.4,
    minor_axis=0.2
)

# 创建弯曲路径
path_points = [
    make_point(0, 0, 0),
    make_point(2, 1, 0),
    make_point(4, 0, 1),
    make_point(6, -1, 1)
]
curved_path = make_spline(path_points)

elliptical_tube = sweep(ellipse_profile, curved_path)
```

### 椭圆在机械设计中的应用
```python
from simplecadapi import *
import math

# 创建椭圆形凸轮轮廓
cam_center = make_point(0, 0, 0)
cam_profile = make_ellipse(
    center=cam_center,
    major_axis=3.0,
    minor_axis=2.0,
    rotation=0
)

# 拉伸成凸轮
cam_thickness = 0.3
cam_body = extrude(cam_profile, distance=cam_thickness)

# 在中心添加轴孔
shaft_hole = make_circle(0.2)
shaft = extrude(shaft_hole, distance=cam_thickness * 1.1)

cam_with_hole = cut(cam_body, shaft)
```

## 注意事项
- 椭圆使用32边形近似，比圆形（16边形）更精确
- major_axis应该大于等于minor_axis，但函数会自动处理
- rotation参数使用弧度制，不是角度制
- 椭圆在XY平面内创建，以指定的center为中心
- 当major_axis = minor_axis时，椭圆退化为圆形
- 适用于需要非对称截面的设计，如管道、结构件等
