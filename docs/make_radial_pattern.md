# make_radial_pattern

## 定义
```python
def make_radial_pattern(body: Body, 
                   center: Point, 
                   axis: Tuple[float, float, float],
                   count: int, 
                   angle: float) -> Body
```

## 作用
创建实体的径向（环形）阵列。该函数将输入实体围绕指定轴心旋转复制，创建圆形或扇形分布的阵列。常用于创建齿轮齿、花瓣模式、螺栓孔圆周分布等。

**参数说明：**
- `body`: 要阵列的源实体
- `center`: 旋转中心点
- `axis`: 旋转轴向量 (x, y, z)
- `count`: 阵列总数量（包括原始实体）
- `angle`: 总角度范围（弧度），2π表示完整圆形

**返回值：**
- 返回包含所有阵列实体的 Body 对象

## 示例代码

### 基础圆形阵列
```python
from simplecadapi.operations import *
import math

# 创建基础形状
base_rect = make_rectangle(4, 8)
base_shape = extrude(base_rect, 10)

# 移动到距离中心一定距离的位置
# （实际应用中可能需要先平移基础形状）

# 创建完整圆形阵列（360度）
center_point = make_point(0, 0, 0)
circular_array = make_radial_pattern(
    body=base_shape,
    center=center_point,
    axis=(0, 0, 1),         # Z轴旋转
    count=8,                # 8个实体
    angle=2 * math.pi       # 360度（2π弧度）
)

export_stl(circular_array, "output/radial_array_full.stl")
```

### 扇形阵列
```python
from simplecadapi.operations import *
import math

# 创建圆柱体作为基础
cylinder = make_cylinder(radius=3, height=15)

# 创建120度扇形阵列
center_point = make_point(0, 0, 0)
fan_array = make_radial_pattern(
    body=cylinder,
    center=center_point,
    axis=(0, 0, 1),
    count=5,                        # 5个实体
    angle=math.pi * 2 / 3          # 120度
)

export_stl(fan_array, "output/radial_array_fan.stl")
```

### 齿轮齿模拟
```python
from simplecadapi.operations import *
import math

# 创建齿形状
tooth_points = [
    make_point(8, -1, 0),
    make_point(10, -0.5, 0),
    make_point(10, 0.5, 0),
    make_point(8, 1, 0),
    make_point(8, -1, 0)
]
tooth_lines = [make_segement(tooth_points[i], tooth_points[i+1]) 
               for i in range(len(tooth_points)-1)]
tooth_sketch = make_sketch(tooth_lines)
tooth = extrude(tooth_sketch, 5)

# 创建齿轮齿阵列
center_point = make_point(0, 0, 0)
gear_teeth = make_radial_pattern(
    body=tooth,
    center=center_point,
    axis=(0, 0, 1),
    count=12,               # 12个齿
    angle=2 * math.pi       # 完整圆形
)

# 创建齿轮基体
gear_base = make_cylinder(radius=8, height=5)
gear = union(gear_base, gear_teeth)

export_stl(gear, "output/simple_gear.stl")
```

### 花瓣模式
```python
from simplecadapi.operations import *
import math

# 创建花瓣形状
petal_circle = make_circle(radius=3)
petal = extrude(petal_circle, 2)

# 创建花瓣阵列
center_point = make_point(0, 0, 0)
flower = make_radial_pattern(
    body=petal,
    center=center_point,
    axis=(0, 0, 1),
    count=6,                # 6个花瓣
    angle=2 * math.pi
)

export_stl(flower, "output/flower_pattern.stl")
```

### 螺栓孔圆周分布
```python
from simplecadapi.operations import *
import math

# 创建基础法兰盘
flange = make_cylinder(radius=25, height=8)

# 创建螺栓孔
bolt_hole = make_cylinder(radius=2, height=10)

# 将孔移动到合适位置（距离中心15单位）
# 注意：实际应用中需要先平移孔的位置

# 创建孔的圆周阵列
center_point = make_point(0, 0, 0)
bolt_holes = make_radial_pattern(
    body=bolt_hole,
    center=center_point,
    axis=(0, 0, 1),
    count=6,                # 6个螺栓孔
    angle=2 * math.pi
)

# 从法兰盘中减去螺栓孔
flange_with_holes = cut(flange, bolt_holes)
export_stl(flange_with_holes, "output/flange_with_bolt_holes.stl")
```

### 不同轴向的径向阵列
```python
from simplecadapi.operations import *
import math

# 创建基础形状
base_box = make_box(3, 3, 8, center=True)

# 围绕X轴的径向阵列
center_point = make_point(0, 0, 0)
x_axis_array = make_radial_pattern(
    body=base_box,
    center=center_point,
    axis=(1, 0, 0),         # 围绕X轴
    count=8,
    angle=2 * math.pi
)

# 围绕Y轴的径向阵列  
y_axis_array = make_radial_pattern(
    body=base_box,
    center=center_point,
    axis=(0, 1, 0),         # 围绕Y轴
    count=6,
    angle=math.pi           # 180度
)

export_stl(x_axis_array, "output/radial_array_x_axis.stl")
export_stl(y_axis_array, "output/radial_array_y_axis.stl")
```

### 复杂几何的径向阵列
```python
from simplecadapi.operations import *
import math

# 创建复杂的基础形状
base_rect = make_rectangle(3, 6)
base_body = extrude(base_rect, 8)

# 添加装饰圆柱
deco_circle = make_circle(1)
deco_cylinder = extrude(deco_circle, 12)

# 合并形状
complex_shape = union(base_body, deco_cylinder)

# 创建径向阵列
center_point = make_point(0, 0, 0)
complex_radial = make_radial_pattern(
    body=complex_shape,
    center=center_point,
    axis=(0, 0, 1),
    count=10,
    angle=2 * math.pi
)

export_stl(complex_radial, "output/complex_radial_array.stl")
```

## 注意事项
1. `count` 必须大于等于2，因为径向阵列至少需要2个实体
2. `angle` 为弧度值，2π表示完整圆形，π表示半圆
3. 当 `angle` 接近2π时，算法会自动调整为完整圆形分布
4. 对于部分扇形，实体会均匀分布在指定角度范围内
5. 旋转轴向量会被自动标准化
6. 确保基础实体与旋转中心的位置关系合理，避免自相交
7. 径向阵列会合并所有实体为单一 Body 对象
