# union 函数文档

## 定义
```python
def union(body1: Body, body2: Body) -> Body
```

## 作用
执行布尔并运算，将两个实体合并成一个单一的实体。重叠部分会自动合并，是组装和连接零件的基础操作。

## 参数
- `body1` (Body): 第一个实体
- `body2` (Body): 第二个实体

## 返回值
- `Body`: 布尔并运算后的合并实体

## 示例代码

### 基础并运算（来自comprehensive_test）
```python
from simplecadapi import *

# 创建两个立方体并合并
box1 = make_box(2.0, 2.0, 1.0, center=True)
box2 = make_box(1.5, 1.5, 1.5, center=True)

union_result = union(box1, box2)
```

### 圆柱体合并
```python
from simplecadapi import *

# 创建T形管道连接
main_pipe = make_cylinder(0.5, 4.0)

# 在中间位置添加侧管
with LocalCoordinateSystem(origin=(0, 0, 2.0), x_axis=(0, 1, 0), y_axis=(1, 0, 0)):
    side_pipe = make_cylinder(0.4, 3.0)

t_junction = union(main_pipe, side_pipe)
```

### 复杂结构组装
```python
from simplecadapi import *

# 创建支架基座
base_plate = make_box(6.0, 4.0, 0.5, center=True)

# 添加立柱
column_positions = [(-2, -1.5), (2, -1.5), (2, 1.5), (-2, 1.5)]
support_structure = base_plate

for x, y in column_positions:
    with LocalCoordinateSystem(origin=(x, y, 0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        column = make_cylinder(0.3, 2.0)
        support_structure = union(support_structure, column)

# 添加顶板
with LocalCoordinateSystem(origin=(0, 0, 2.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    top_plate = make_box(6.0, 4.0, 0.3, center=True)
    complete_frame = union(support_structure, top_plate)
```

### 机械零件组装
```python
from simplecadapi import *

# 创建轴承座
bearing_base = make_box(4.0, 3.0, 2.0, center=True)

# 添加轴承孔座
with LocalCoordinateSystem(origin=(0, 0, 2.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    bearing_boss = make_cylinder(1.8, 1.0)
    bearing_assembly = union(bearing_base, bearing_boss)

# 添加安装脚
foot_positions = [(-1.5, -1.0), (1.5, -1.0), (1.5, 1.0), (-1.5, 1.0)]

for x, y in foot_positions:
    with LocalCoordinateSystem(origin=(x, y, -1.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        mounting_foot = make_cylinder(0.4, 1.0)
        bearing_assembly = union(bearing_assembly, mounting_foot)
```

### 容器组装
```python
from simplecadapi import *

# 创建容器主体
container_body = make_cylinder(2.0, 3.0)

# 添加底部
bottom_plate = make_cylinder(2.2, 0.2)
container_with_bottom = union(container_body, bottom_plate)

# 添加把手
with LocalCoordinateSystem(origin=(2.5, 0, 1.5), x_axis=(0, 1, 0), y_axis=(0, 0, 1)):
    handle = make_cylinder(0.2, 1.5)
    container_with_handle = union(container_with_bottom, handle)

# 添加倒嘴
with LocalCoordinateSystem(origin=(1.8, 0, 2.8), x_axis=(0, 1, 0), y_axis=(1, 0, 0)):
    spout = make_cylinder(0.3, 0.8)
    complete_container = union(container_with_handle, spout)
```

### 齿轮制造
```python
from simplecadapi import *
import math

# 创建齿轮基体
gear_hub = make_cylinder(1.0, 0.8)

# 添加齿轮齿（简化为小立方体）
gear_with_teeth = gear_hub
tooth_count = 12

for i in range(tooth_count):
    angle = i * 2 * math.pi / tooth_count
    x = 2.0 * math.cos(angle)
    y = 2.0 * math.sin(angle)
    
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        tooth = make_box(0.4, 0.6, 0.8, center=True)
        gear_with_teeth = union(gear_with_teeth, tooth)

# 添加轮毂加强筋
hub_ring = make_cylinder(1.5, 0.8)
reinforced_gear = union(gear_with_teeth, hub_ring)
```

### 管道系统组装
```python
from simplecadapi import *

# 主管道
main_line = make_cylinder(0.3, 10.0)

# 分支管道
branch_pipes = main_line

# 添加T形分支
branch_positions = [2.0, 5.0, 8.0]

for z_pos in branch_positions:
    with LocalCoordinateSystem(origin=(0, 0, z_pos), x_axis=(0, 1, 0), y_axis=(1, 0, 0)):
        branch = make_cylinder(0.25, 2.0)
        branch_pipes = union(branch_pipes, branch)

# 添加弯头连接
with LocalCoordinateSystem(origin=(0, 0, 10.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    elbow_vertical = make_cylinder(0.3, 1.5)
    
with LocalCoordinateSystem(origin=(1.5, 0, 10.0), x_axis=(0, 1, 0), y_axis=(1, 0, 0)):
    elbow_horizontal = make_cylinder(0.3, 2.0)

pipe_system = union(branch_pipes, elbow_vertical)
pipe_system = union(pipe_system, elbow_horizontal)
```

### 建筑结构组装
```python
from simplecadapi import *

# 创建建筑框架
# 底层梁
floor_beam_1 = make_box(10.0, 0.3, 0.5, center=True)

with LocalCoordinateSystem(origin=(0, 3.0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    floor_beam_2 = make_box(10.0, 0.3, 0.5, center=True)

floor_beams = union(floor_beam_1, floor_beam_2)

# 添加柱子
column_positions = [(-4.5, -1.5), (0, -1.5), (4.5, -1.5), 
                   (-4.5, 1.5), (0, 1.5), (4.5, 1.5)]

building_frame = floor_beams

for x, y in column_positions:
    with LocalCoordinateSystem(origin=(x, y, 0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        column = make_box(0.4, 0.4, 4.0, center=True)
        building_frame = union(building_frame, column)

# 添加屋顶梁
with LocalCoordinateSystem(origin=(0, 0, 4.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    roof_beam = make_box(10.0, 0.3, 0.5, center=True)
    complete_frame = union(building_frame, roof_beam)
```

### 电子设备外壳组装
```python
from simplecadapi import *

# 主外壳
main_case = make_box(8.0, 6.0, 2.0, center=True)

# 添加散热片
heat_sink_base = main_case

fin_count = 5
fin_spacing = 1.2

for i in range(fin_count):
    x_pos = -2.4 + i * fin_spacing
    
    with LocalCoordinateSystem(origin=(x_pos, 0, 2.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        fin = make_box(0.1, 6.0, 1.0, center=True)
        heat_sink_base = union(heat_sink_base, fin)

# 添加连接器外壳
with LocalCoordinateSystem(origin=(4.0, 0, 0), x_axis=(0, 1, 0), y_axis=(0, 0, 1)):
    connector_housing = make_cylinder(0.8, 1.0)
    electronics_case = union(heat_sink_base, connector_housing)
```

### 多个零件的顺序组装
```python
from simplecadapi import *

# 创建组装序列
components = []

# 基础部件
base = make_box(3.0, 3.0, 0.5, center=True)
components.append(base)

# 支撑柱
with LocalCoordinateSystem(origin=(0, 0, 0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    pillar = make_cylinder(0.5, 2.0)
    components.append(pillar)

# 顶板
with LocalCoordinateSystem(origin=(0, 0, 2.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    top_plate = make_box(2.0, 2.0, 0.3, center=True)
    components.append(top_plate)

# 装饰环
with LocalCoordinateSystem(origin=(0, 0, 1.25), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    ring_outer = make_cylinder(0.8, 0.2)
    ring_inner = make_cylinder(0.6, 0.3)
    decorative_ring = cut(ring_outer, ring_inner)
    components.append(decorative_ring)

# 逐步组装
assembly = components[0]
for component in components[1:]:
    assembly = union(assembly, component)
```

### 组装验证
```python
from simplecadapi import *

# 创建两个测试对象
part1 = make_box(2.0, 2.0, 1.0, center=True)
part2 = make_cylinder(1.0, 2.0)

try:
    assembled = union(part1, part2)
    
    if assembled.is_valid():
        print("组装操作成功")
    else:
        print("组装产生无效几何体")
        
except Exception as e:
    print(f"组装操作失败: {e}")
```

## 注意事项
- 两个实体可以有重叠、相切或分离，union都会将它们合并
- 如果两个实体完全分离，结果是包含两个独立部分的复合体
- 重叠部分会自动处理，不会产生重复材料
- union操作是可交换的：union(A, B) = union(B, A)
- 连续的union操作可以组装多个零件
- 适用于零件组装、结构连接、复杂形状构建
- 是CAD设计中构建复杂几何体的基础操作
- 组装后的实体可以进行进一步的加工操作（切削、圆角等）
