# make_cylinder 函数文档

## 定义
```python
def make_cylinder(radius: float, height: float) -> Body
```

## 作用
直接创建圆柱体3D实体。这是创建基础旋转体的便捷函数，自动生成带标签的圆柱体。

## 参数
- `radius` (float): 圆柱体半径
- `height` (float): 圆柱体高度

## 返回值
- `Body`: 圆柱体实体，自动添加面标签

## 示例代码

### 基础圆柱体创建（来自comprehensive_test）
```python
from simplecadapi import *

# 创建简单圆柱体
cylinder = make_cylinder(0.6, 2.0)

# 用于布尔减运算
box1 = make_box(2.0, 2.0, 1.0, center=True)
cut_result = cut(box1, cylinder)
```

### 不同尺寸的圆柱体
```python
from simplecadapi import *

# 细长圆柱（如轴）
shaft = make_cylinder(0.5, 10.0)

# 扁平圆柱（如垫片）
washer = make_cylinder(2.0, 0.2)

# 标准圆柱
standard_cylinder = make_cylinder(1.0, 2.0)

# 大直径圆柱（如储罐）
tank = make_cylinder(5.0, 8.0)
```

### 管道制作
```python
from simplecadapi import *

# 外管
outer_pipe = make_cylinder(2.0, 5.0)

# 内孔
inner_hole = make_cylinder(1.8, 5.2)  # 稍长确保完全切穿

# 创建管道
pipe = cut(outer_pipe, inner_hole)
```

### 轴承制作
```python
from simplecadapi import *

# 外圈
bearing_outer = make_cylinder(3.0, 1.0)

# 内孔
bearing_inner = make_cylinder(1.5, 1.2)

# 轴承套圈
bearing_ring = cut(bearing_outer, bearing_inner)

# 添加滚珠槽（简化）
with LocalCoordinateSystem(origin=(0, 0, 0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    ball_groove = make_cylinder(2.8, 0.3)
    bearing_with_groove = cut(bearing_ring, ball_groove)
```

### 螺栓制作
```python
from simplecadapi import *

# 螺栓杆
bolt_shaft = make_cylinder(0.5, 4.0)

# 螺栓头
with LocalCoordinateSystem(origin=(0, 0, 4.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    bolt_head = make_cylinder(1.0, 0.8)

# 组装螺栓
bolt = union(bolt_shaft, bolt_head)
```

### 在不同坐标系中创建
```python
from simplecadapi import *

# 水平圆柱体（绕Y轴）
with LocalCoordinateSystem(
    origin=(0, 0, 1),
    x_axis=(0, 1, 0),    # Y轴作为新的X轴
    y_axis=(0, 0, 1)     # Z轴作为新的Y轴
):
    horizontal_cylinder = make_cylinder(0.8, 6.0)

# 斜向圆柱体
import math
angle = math.pi / 4  # 45度
with LocalCoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(math.cos(angle), 0, math.sin(angle)),
    y_axis=(0, 1, 0)
):
    tilted_cylinder = make_cylinder(0.5, 3.0)
```

### 机械零件应用
```python
from simplecadapi import *

# 创建支撑柱
support_base = make_box(4.0, 4.0, 0.5, center=True)

# 添加圆柱形支撑
with LocalCoordinateSystem(origin=(0, 0, 0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    support_column = make_cylinder(0.8, 3.0)

# 添加顶部平台
with LocalCoordinateSystem(origin=(0, 0, 3.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    top_platform = make_cylinder(1.5, 0.3)

# 组装支撑结构
support_assembly = union(support_base, support_column)
support_assembly = union(support_assembly, top_platform)
```

### 容器制作
```python
from simplecadapi import *

# 圆柱形容器
container_outer = make_cylinder(3.0, 5.0)

# 内部空腔
container_inner = make_cylinder(2.8, 4.8)

# 创建容器壁
container_walls = cut(container_outer, container_inner)

# 添加底部
bottom_plate = make_cylinder(3.0, 0.2)

# 完整容器
complete_container = union(container_walls, bottom_plate)
```

### 轮子制作
```python
from simplecadapi import *

# 轮胎
tire_outer = make_cylinder(4.0, 1.5)
tire_inner = make_cylinder(2.5, 1.6)
tire = cut(tire_outer, tire_inner)

# 轮毂
hub = make_cylinder(2.4, 1.5)

# 中心孔
center_hole = make_cylinder(0.8, 1.6)
hub_with_hole = cut(hub, center_hole)

# 辐条孔（简化）
import math
wheel_assembly = union(tire, hub_with_hole)

for i in range(5):
    angle = i * 2 * math.pi / 5
    x = 1.5 * math.cos(angle)
    y = 1.5 * math.sin(angle)
    
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        spoke_hole = make_cylinder(0.2, 1.6)
        wheel_assembly = cut(wheel_assembly, spoke_hole)
```

### 柱状结构阵列
```python
from simplecadapi import *

# 基础柱子
base_column = make_cylinder(0.3, 4.0)

# 创建柱子阵列
column_positions = []
import math

# 圆形排列
radius = 5.0
column_count = 8

for i in range(column_count):
    angle = i * 2 * math.pi / column_count
    x = radius * math.cos(angle)
    y = radius * math.sin(angle)
    column_positions.append((x, y))

# 创建柱子群
colonnade = base_column

for x, y in column_positions[1:]:  # 跳过第一个（已经在原点）
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        column = make_cylinder(0.3, 4.0)
        colonnade = union(colonnade, column)
```

### 工具和模具
```python
from simplecadapi import *

# 冲压模具
# 上模
upper_die = make_cylinder(4.0, 2.0)

# 冲压头
with LocalCoordinateSystem(origin=(0, 0, -0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    punch = make_cylinder(1.5, 1.0)

# 模具导向柱
guide_positions = [(2.5, 2.5), (-2.5, 2.5), (2.5, -2.5), (-2.5, -2.5)]
die_assembly = union(upper_die, punch)

for x, y in guide_positions:
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        guide_pin = make_cylinder(0.2, 3.0)
        die_assembly = union(die_assembly, guide_pin)
```

### 发动机零件
```python
from simplecadapi import *

# 气缸体（简化）
cylinder_block = make_cylinder(5.0, 8.0)

# 活塞孔
piston_bore = make_cylinder(4.0, 8.2)
cylinder_with_bore = cut(cylinder_block, piston_bore)

# 冷却水套
cooling_jacket = make_cylinder(4.5, 8.0)
water_jacket = cut(cooling_jacket, piston_bore)

# 排气孔
with LocalCoordinateSystem(origin=(3.0, 0, 6.0), x_axis=(0, 1, 0), y_axis=(1, 0, 0)):
    exhaust_port = make_cylinder(0.8, 2.0)
    cylinder_with_exhaust = cut(cylinder_with_bore, exhaust_port)
```

### 建筑圆柱
```python
from simplecadapi import *

# 建筑圆柱
architectural_column = make_cylinder(1.0, 6.0)

# 柱头装饰
with LocalCoordinateSystem(origin=(0, 0, 6.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    capital = make_cylinder(1.3, 0.5)

# 柱脚
column_base = make_cylinder(1.2, 0.3)

# 组装古典柱
classical_column = union(architectural_column, capital)
classical_column = union(classical_column, column_base)
```

### 测试和验证
```python
from simplecadapi import *

# 创建测试圆柱体
test_cylinder = make_cylinder(1.0, 2.0)

# 验证圆柱体属性
if test_cylinder.is_valid():
    print("圆柱体创建成功")
    
    # 检查面标签（make_cylinder自动添加面标签）
    face_info = get_face_info(test_cylinder)
    print(f"圆柱体有 {face_info['total_faces']} 个面")
    print(f"标签面: {face_info['tagged_faces']}")
else:
    print("圆柱体创建失败")

# 参数验证
try:
    invalid_cylinder = make_cylinder(-1.0, 2.0)  # 负半径
except Exception as e:
    print(f"参数验证成功: {e}")
```

## 注意事项
- radius和height必须为正值
- 圆柱体的轴线沿着当前坐标系的Z轴方向
- 圆柱体底面位于当前坐标系的XY平面（Z=0）
- 自动添加面标签："top", "bottom", "side"
- 面标签便于后续的面选择操作
- 圆柱体是旋转对称的，适用于轴类、管道、容器等设计
- 可以通过布尔运算创建复杂的圆柱形结构
- 在不同坐标系中创建可以改变圆柱体的方向
- 常用于机械零件、建筑元素、容器设计等
