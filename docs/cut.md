# cut 函数文档

## 定义
```python
def cut(target: Body, tool: Body) -> Body
```

## 作用
执行布尔减运算，从目标实体中减去工具实体，创建切削、开孔、槽口等效果。这是CAD中最常用的布尔运算之一。

## 参数
- `target` (Body): 目标实体（被切削的对象）
- `tool` (Body): 工具实体（用于切削的对象）

## 返回值
- `Body`: 布尔减运算后的实体

## 示例代码

### 基础孔洞切削（来自comprehensive_test）
```python
from simplecadapi import *

# 创建测试实体
box1 = make_box(2.0, 2.0, 1.0, center=True)
cylinder = make_cylinder(0.6, 2.0)

# 布尔减运算
cut_result = cut(box1, cylinder)
```

### 圆形孔洞
```python
from simplecadapi import *

# 在板材上开圆孔
plate = make_box(5.0, 3.0, 0.5, center=True)
hole = make_cylinder(0.5, 1.0)  # 穿透孔

plate_with_hole = cut(plate, hole)
```

### 方形槽口
```python
from simplecadapi import *

# 创建带槽口的零件
main_block = make_box(4.0, 2.0, 2.0, center=True)

# 创建槽口
slot = make_box(3.0, 0.5, 2.5, center=True)  # 稍高确保完全切穿

slotted_block = cut(main_block, slot)
```

### 复杂切削形状
```python
from simplecadapi import *

# 创建复杂的切削特征
base_cylinder = make_cylinder(2.0, 3.0)

# 创建六边形切削工具
import math
hex_points = []
for i in range(6):
    angle = i * math.pi / 3
    x = 1.0 * math.cos(angle)
    y = 1.0 * math.sin(angle)
    hex_points.append(make_point(x, y, 0))

hex_lines = []
for i in range(6):
    p1 = hex_points[i]
    p2 = hex_points[(i + 1) % 6]
    hex_lines.append(make_segement(p1, p2))

hex_profile = make_sketch(hex_lines)
hex_cutter = extrude(hex_profile, distance=3.5)

# 切削出六边形内孔
hex_socket = cut(base_cylinder, hex_cutter)
```

### 键槽切削
```python
from simplecadapi import *

# 创建轴
shaft = make_cylinder(1.0, 5.0)

# 创建键槽
keyway_profile = make_rectangle(0.3, 1.0, center=True)
keyway_cutter = extrude(keyway_profile, distance=6.0)

# 切削键槽
keyed_shaft = cut(shaft, keyway_cutter)
```

### 螺纹孔切削
```python
from simplecadapi import *

# 创建需要螺纹孔的零件
housing = make_box(6.0, 4.0, 2.0, center=True)

# 创建螺纹孔（简化为圆孔）
thread_hole = make_cylinder(0.4, 2.5)

# 在不同位置切削螺纹孔
housing_with_holes = housing

# 四个角上的螺纹孔
positions = [(-2, -1.5), (2, -1.5), (2, 1.5), (-2, 1.5)]

for x, y in positions:
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        hole = make_cylinder(0.2, 2.5)
        housing_with_holes = cut(housing_with_holes, hole)
```

### 斜面切削
```python
from simplecadapi import *

# 创建基础立方体
cube = make_box(3.0, 3.0, 3.0, center=True)

# 创建斜面切削工具
chamfer_points = [
    make_point(-2, -2, 1.5),
    make_point(2, -2, 1.5),
    make_point(2, 2, 1.5),
    make_point(-2, 2, 1.5),
    make_point(-2, -2, 4),
    make_point(2, -2, 4),
    make_point(2, 2, 4),
    make_point(-2, 2, 4)
]

# 简化：使用矩形向上拉伸作为切削工具
chamfer_profile = make_rectangle(5.0, 5.0, center=True)
with LocalCoordinateSystem(origin=(0, 0, 1.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    chamfer_cutter = extrude(chamfer_profile, distance=3.0)

chamfered_cube = cut(cube, chamfer_cutter)
```

### 环形切削
```python
from simplecadapi import *

# 创建环形零件
outer_cylinder = make_cylinder(3.0, 1.0)
inner_cylinder = make_cylinder(2.0, 1.2)  # 稍高确保完全切穿

ring = cut(outer_cylinder, inner_cylinder)
```

### 复杂容器制作
```python
from simplecadapi import *

# 创建瓶子外形
bottle_outer = make_cylinder(2.0, 4.0)

# 创建内部空腔
bottle_inner = make_cylinder(1.7, 3.8)

# 切削出空腔
bottle_shell = cut(bottle_outer, bottle_inner)

# 创建瓶口
with LocalCoordinateSystem(origin=(0, 0, 4.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    neck_outer = make_cylinder(0.8, 0.5)
    neck_inner = make_cylinder(0.6, 0.6)
    neck = cut(neck_outer, neck_inner)

complete_bottle = union(bottle_shell, neck)
```

### 齿轮齿切削
```python
from simplecadapi import *
import math

# 创建齿轮基体
gear_blank = make_cylinder(3.0, 0.8)

# 切削齿间空隙
gear_with_teeth = gear_blank
tooth_count = 12

for i in range(tooth_count):
    angle = i * 2 * math.pi / tooth_count
    x = 2.5 * math.cos(angle)
    y = 2.5 * math.sin(angle)
    
    # 创建齿间切削工具
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        tooth_gap = make_box(0.3, 0.8, 1.0, center=True)
        gear_with_teeth = cut(gear_with_teeth, tooth_gap)

# 切削中心孔
center_hole = make_cylinder(0.5, 1.0)
finished_gear = cut(gear_with_teeth, center_hole)
```

### 多级切削
```python
from simplecadapi import *

# 创建分级轴
shaft_base = make_cylinder(2.0, 5.0)

# 第一级切削（大直径部分）
stage1_cutter = make_cylinder(1.8, 2.0)
shaft_step1 = cut(shaft_base, stage1_cutter)

# 第二级切削（中等直径部分）
with LocalCoordinateSystem(origin=(0, 0, 2.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    stage2_cutter = make_cylinder(1.5, 2.0)
    shaft_step2 = cut(shaft_step1, stage2_cutter)

# 第三级切削（小直径部分）
with LocalCoordinateSystem(origin=(0, 0, 4.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    stage3_cutter = make_cylinder(1.0, 1.2)
    stepped_shaft = cut(shaft_step2, stage3_cutter)
```

### 精密切削特征
```python
from simplecadapi import *

# 创建精密零件基体
precision_block = make_box(4.0, 3.0, 2.0, center=True)

# 创建精密孔系
# 主孔
main_hole = make_cylinder(0.8, 2.5)
block_with_main = cut(precision_block, main_hole)

# 销孔
with LocalCoordinateSystem(origin=(1.5, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    pin_hole = make_cylinder(0.2, 2.5)
    block_with_pin = cut(block_with_main, pin_hole)

# 定位孔
with LocalCoordinateSystem(origin=(-1.5, 1.0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    locating_hole = make_cylinder(0.15, 2.5)
    precision_part = cut(block_with_pin, locating_hole)
```

### 切削操作验证
```python
from simplecadapi import *

# 创建测试对象
test_target = make_box(2.0, 2.0, 2.0, center=True)
test_tool = make_cylinder(0.5, 3.0)

try:
    result = cut(test_target, test_tool)
    
    if result.is_valid():
        print("切削操作成功")
    else:
        print("切削操作产生无效几何体")
        
except Exception as e:
    print(f"切削操作失败: {e}")
```

## 注意事项
- 工具实体应该与目标实体有重叠部分，否则切削无效果
- 工具实体通常应该比目标实体在切削方向上更长，确保完全切穿
- 切削操作可能产生复杂的几何体，影响后续操作性能
- 如果工具完全包含目标，结果可能是空几何体
- 适用于创建孔洞、槽口、切削特征、空腔等
- 是机械设计中最常用的布尔运算
- 可以连续使用多个cut操作创建复杂的切削特征
