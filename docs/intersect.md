# intersect 函数文档

## 定义
```python
def intersect(body1: Body, body2: Body) -> Body
```

## 作用
执行布尔交运算，保留两个实体的重叠部分，删除不重叠的部分。常用于提取公共部分、创建复杂配合特征。

## 参数
- `body1` (Body): 第一个实体
- `body2` (Body): 第二个实体

## 返回值
- `Body`: 布尔交运算后的实体（两实体的重叠部分）

## 示例代码

### 基础交运算（来自comprehensive_test）
```python
from simplecadapi import *

# 创建两个重叠的立方体
box1 = make_box(2.0, 2.0, 1.0, center=True)
box2 = make_box(1.5, 1.5, 1.5, center=True)

intersect_result = intersect(box1, box2)
```

### 圆柱体相交
```python
from simplecadapi import *

# 创建两个垂直相交的圆柱体
cylinder1 = make_cylinder(1.0, 4.0)

with LocalCoordinateSystem(origin=(0, 0, 2.0), x_axis=(0, 1, 0), y_axis=(1, 0, 0)):
    cylinder2 = make_cylinder(0.8, 4.0)

intersection_shape = intersect(cylinder1, cylinder2)
```

### 球体与立方体相交
```python
from simplecadapi import *

# 创建球体和立方体的交集
sphere = make_sphere(1.5)
cube = make_box(2.0, 2.0, 2.0, center=True)

rounded_cube = intersect(sphere, cube)
```

### 复杂形状相交
```python
from simplecadapi import *

# 创建圆柱体
base_cylinder = make_cylinder(2.0, 3.0)

# 创建椭圆柱体
ellipse_profile = make_ellipse(
    make_point(0, 0, 0),
    major_axis=3.0,
    minor_axis=1.5
)
ellipse_cylinder = extrude(ellipse_profile, distance=3.5)

# 获取交集
complex_intersection = intersect(base_cylinder, ellipse_cylinder)
```

### 齿轮齿形提取
```python
from simplecadapi import *
import math

# 创建齿轮毛坯
gear_blank = make_cylinder(3.0, 0.8)

# 创建齿形模板
tooth_template = make_cylinder(2.8, 1.0)

# 创建齿间空隙
tooth_cutters = []
tooth_count = 12

for i in range(tooth_count):
    angle = i * 2 * math.pi / tooth_count
    x = 2.5 * math.cos(angle)
    y = 2.5 * math.sin(angle)
    
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        tooth_gap = make_box(0.4, 1.0, 1.0, center=True)
        tooth_cutters.append(tooth_gap)

# 从模板中减去齿间空隙
gear_profile = tooth_template
for cutter in tooth_cutters:
    gear_profile = cut(gear_profile, cutter)

# 与毛坯求交，得到最终齿轮
final_gear = intersect(gear_blank, gear_profile)
```

### 管道连接处分析
```python
from simplecadapi import *

# 创建主管道
main_pipe = make_cylinder(1.0, 6.0)

# 创建分支管道
with LocalCoordinateSystem(origin=(0, 0, 3.0), x_axis=(0, 1, 0), y_axis=(1, 0, 0)):
    branch_pipe = make_cylinder(0.8, 4.0)

# 分析连接处的重叠区域
connection_zone = intersect(main_pipe, branch_pipe)
```

### 配合面分析
```python
from simplecadapi import *

# 创建轴
shaft = make_cylinder(1.0, 5.0)

# 创建轴承孔
bearing_hole = make_cylinder(1.02, 2.0)  # 稍大的间隙

# 分析配合区域
with LocalCoordinateSystem(origin=(0, 0, 1.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    mating_region = intersect(shaft, bearing_hole)
```

### 加工余量分析
```python
from simplecadapi import *

# 毛坯
rough_part = make_box(5.0, 3.0, 2.0, center=True)

# 成品设计
finish_part = make_box(4.5, 2.5, 1.8, center=True)

# 分析需要保留的材料
material_to_keep = intersect(rough_part, finish_part)
```

### 工具与工件重叠分析
```python
from simplecadapi import *

# 工件
workpiece = make_cylinder(3.0, 4.0)

# 刀具路径（简化为圆柱体）
with LocalCoordinateSystem(origin=(1.5, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    cutting_tool = make_cylinder(0.5, 5.0)

# 分析切削重叠区域
cutting_overlap = intersect(workpiece, cutting_tool)
```

### 容积分析
```python
from simplecadapi import *

# 外容器
outer_container = make_cylinder(2.0, 3.0)

# 内容器
with LocalCoordinateSystem(origin=(0.5, 0, 0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    inner_container = make_cylinder(1.2, 2.0)

# 分析重叠容积
overlap_volume = intersect(outer_container, inner_container)
```

### 复杂几何体相交
```python
from simplecadapi import *

# 创建扭转体
base_rect = make_rectangle(2.0, 0.5, center=True)
sections = [base_rect]

# 创建多个旋转截面
import math
for i in range(1, 6):
    angle = i * math.pi / 10
    height = i * 0.5
    
    with LocalCoordinateSystem(
        origin=(0, 0, height),
        x_axis=(math.cos(angle), math.sin(angle), 0),
        y_axis=(-math.sin(angle), math.cos(angle), 0)
    ):
        section = make_rectangle(2.0, 0.5, center=True)
        sections.append(section)

twisted_shape = loft(sections)

# 与圆柱体相交
cylinder = make_cylinder(1.5, 3.0)
twisted_cylinder = intersect(twisted_shape, cylinder)
```

### 多体相交
```python
from simplecadapi import *

# 创建三个相交的圆柱体
cylinder_x = make_cylinder(1.0, 6.0)

with LocalCoordinateSystem(origin=(0, 0, 3.0), x_axis=(0, 1, 0), y_axis=(1, 0, 0)):
    cylinder_y = make_cylinder(1.0, 6.0)

with LocalCoordinateSystem(origin=(0, 3.0, 3.0), x_axis=(1, 0, 0), y_axis=(0, 0, 1)):
    cylinder_z = make_cylinder(1.0, 6.0)

# 逐步求交
intersection_xy = intersect(cylinder_x, cylinder_y)
intersection_xyz = intersect(intersection_xy, cylinder_z)
```

### 精密配合分析
```python
from simplecadapi import *

# 精密轴
precision_shaft = make_cylinder(0.9995, 3.0)  # 精密直径

# 精密孔
precision_hole = make_cylinder(1.0005, 3.2)  # 精密孔径

# 分析配合区域
with LocalCoordinateSystem(origin=(0, 0, 0.1), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    fit_analysis = intersect(precision_shaft, precision_hole)
```

### 碰撞检测
```python
from simplecadapi import *

# 运动部件1
moving_part1 = make_box(2.0, 1.0, 1.0, center=True)

# 运动部件2（在运动路径上）
with LocalCoordinateSystem(origin=(1.5, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    moving_part2 = make_box(1.5, 0.8, 0.8, center=True)

# 检测碰撞区域
collision_zone = intersect(moving_part1, moving_part2)

# 如果有交集，说明会发生碰撞
if collision_zone.is_valid():
    print("检测到碰撞")
else:
    print("无碰撞")
```

### 相交操作验证
```python
from simplecadapi import *

# 创建测试对象
test_body1 = make_sphere(1.0)
test_body2 = make_box(1.5, 1.5, 1.5, center=True)

try:
    intersection = intersect(test_body1, test_body2)
    
    if intersection.is_valid():
        print("相交操作成功")
    else:
        print("两实体无重叠区域")
        
except Exception as e:
    print(f"相交操作失败: {e}")
```

## 注意事项
- 如果两个实体没有重叠部分，intersect操作可能产生空几何体
- 相交操作是可交换的：intersect(A, B) = intersect(B, A)
- 结果的体积永远不会超过任一输入实体的体积
- 常用于配合分析、碰撞检测、体积计算
- 可以用于提取复杂几何体的特定部分
- 适用于工程分析中的干涉检查
- 相交后的几何体可能具有复杂的边界
- 在精密配合设计中可用于分析配合区域
