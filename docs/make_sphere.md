# make_sphere 函数文档

## 定义
```python
def make_sphere(radius: float) -> Body
```

## 作用
直接创建球体3D实体。球体是完全对称的几何体，常用于轴承、装饰元素、流体建模等应用。

## 参数
- `radius` (float): 球体半径

## 返回值
- `Body`: 球体实体，自动添加面标签

## 示例代码

### 基础球体创建
```python
from simplecadapi import *

# 创建标准球体
sphere = make_sphere(1.5)
```

### 不同尺寸的球体
```python
from simplecadapi import *

# 小球（如滚珠）
ball_bearing = make_sphere(0.2)

# 中等球体（如装饰球）
decorative_sphere = make_sphere(1.0)

# 大球体（如储球罐）
storage_sphere = make_sphere(5.0)
```

### 球体与其他几何体的布尔运算
```python
from simplecadapi import *

# 球体与立方体的交集
sphere = make_sphere(1.5)
cube = make_box(2.0, 2.0, 2.0, center=True)

rounded_cube = intersect(sphere, cube)
```

### 空心球体制作
```python
from simplecadapi import *

# 外球
outer_sphere = make_sphere(2.0)

# 内球
inner_sphere = make_sphere(1.8)

# 球壳
hollow_sphere = cut(outer_sphere, inner_sphere)
```

### 轴承球制作
```python
from simplecadapi import *

# 轴承外圈
bearing_outer = make_cylinder(3.0, 1.0)
bearing_inner_hole = make_cylinder(1.5, 1.2)
bearing_ring = cut(bearing_outer, bearing_inner_hole)

# 滚珠
ball_radius = 0.3
ball_positions = []

import math
ball_count = 8
orbit_radius = 2.25

for i in range(ball_count):
    angle = i * 2 * math.pi / ball_count
    x = orbit_radius * math.cos(angle)
    y = orbit_radius * math.sin(angle)
    ball_positions.append((x, y))

# 添加滚珠到轴承
bearing_with_balls = bearing_ring

for x, y in ball_positions:
    with LocalCoordinateSystem(origin=(x, y, 0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        ball = make_sphere(ball_radius)
        bearing_with_balls = union(bearing_with_balls, ball)
```

### 装饰球体阵列
```python
from simplecadapi import *

# 基础装饰球
decorative_ball = make_sphere(0.5)

# 创建球体阵列
ball_grid = decorative_ball

positions = []
for i in range(-2, 3):
    for j in range(-2, 3):
        if i != 0 or j != 0:  # 跳过原点（已有球）
            positions.append((i * 2.0, j * 2.0))

for x, y in positions:
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        ball = make_sphere(0.5)
        ball_grid = union(ball_grid, ball)
```

### 球形容器
```python
from simplecadapi import *

# 球形储罐
tank_outer = make_sphere(3.0)
tank_inner = make_sphere(2.9)
tank_shell = cut(tank_outer, tank_inner)

# 添加入口管道
with LocalCoordinateSystem(origin=(0, 0, 3.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    inlet_pipe = make_cylinder(0.3, 1.0)
    tank_with_inlet = union(tank_shell, inlet_pipe)

# 添加支撑底座
support_ring = make_cylinder(2.5, 0.3)
complete_tank = union(tank_with_inlet, support_ring)
```

### 分子模型
```python
from simplecadapi import *

# 原子核（大球）
nucleus = make_sphere(0.5)

# 电子（小球）
electron_radius = 0.1
orbital_radius = 1.5

# 电子轨道1
electrons_orbit1 = nucleus

import math
for i in range(4):
    angle = i * math.pi / 2
    x = orbital_radius * math.cos(angle)
    y = orbital_radius * math.sin(angle)
    
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        electron = make_sphere(electron_radius)
        electrons_orbit1 = union(electrons_orbit1, electron)

# 电子轨道2（不同高度）
for i in range(4):
    angle = i * math.pi / 2 + math.pi / 4  # 偏移45度
    x = orbital_radius * math.cos(angle) * 0.8
    y = orbital_radius * math.sin(angle) * 0.8
    z = 0.5
    
    with LocalCoordinateSystem(origin=(x, y, z), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        electron = make_sphere(electron_radius)
        electrons_orbit1 = union(electrons_orbit1, electron)
```

### 珍珠项链模型
```python
from simplecadapi import *

# 珍珠链
pearl_radius = 0.3
chain_radius = 3.0
pearl_count = 12

import math
pearl_necklace = None

for i in range(pearl_count):
    angle = i * 2 * math.pi / pearl_count
    x = chain_radius * math.cos(angle)
    y = chain_radius * math.sin(angle)
    
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        pearl = make_sphere(pearl_radius)
        if pearl_necklace is None:
            pearl_necklace = pearl
        else:
            pearl_necklace = union(pearl_necklace, pearl)
```

### 球形接头
```python
from simplecadapi import *

# 球形接头外壳
joint_outer = make_sphere(2.0)

# 内部球形空腔
joint_inner = make_sphere(1.5)

# 接头座
joint_socket = cut(joint_outer, joint_inner)

# 球形头部
ball_head = make_sphere(1.4)

# 连接杆
with LocalCoordinateSystem(origin=(0, 0, -2.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    connecting_rod = make_cylinder(0.5, 2.0)

# 组装球形接头
ball_joint = union(ball_head, connecting_rod)
```

### 球形灯具
```python
from simplecadapi import *

# 灯罩（球形）
lamp_shade = make_sphere(2.5)

# 灯罩底部开口
with LocalCoordinateSystem(origin=(0, 0, -1.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    bottom_opening = make_cylinder(1.8, 1.0)
    lamp_shade_open = cut(lamp_shade, bottom_opening)

# 顶部电线孔
with LocalCoordinateSystem(origin=(0, 0, 2.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    wire_hole = make_cylinder(0.2, 0.5)
    finished_shade = cut(lamp_shade_open, wire_hole)

# 支撑环
support_ring = make_cylinder(2.0, 0.1)
complete_lamp = union(finished_shade, support_ring)
```

### 球体减材加工模拟
```python
from simplecadapi import *

# 工件（球体）
workpiece = make_sphere(3.0)

# 切削工具路径（多个圆柱体）
machined_sphere = workpiece

# 水平切削
cutting_positions = [-2.0, -1.0, 0.0, 1.0, 2.0]

for z_pos in cutting_positions:
    with LocalCoordinateSystem(origin=(0, 0, z_pos), x_axis=(0, 1, 0), y_axis=(1, 0, 0)):
        cutting_tool = make_cylinder(0.2, 8.0)
        machined_sphere = cut(machined_sphere, cutting_tool)
```

### 球形天体模型
```python
from simplecadapi import *

# 行星系统
# 太阳（中心大球）
sun = make_sphere(1.0)

# 行星轨道
planets_system = sun

planet_data = [
    (2.0, 0.2),   # 距离，半径
    (3.5, 0.3),
    (5.0, 0.25),
    (7.0, 0.15)
]

import math
for i, (orbit_radius, planet_radius) in enumerate(planet_data):
    angle = i * math.pi / 2  # 不同角度位置
    x = orbit_radius * math.cos(angle)
    y = orbit_radius * math.sin(angle)
    
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        planet = make_sphere(planet_radius)
        planets_system = union(planets_system, planet)
```

### 球体质量分析
```python
from simplecadapi import *

# 创建测试球体
test_sphere = make_sphere(2.0)

# 验证球体属性
if test_sphere.is_valid():
    print("球体创建成功")
    
    # 理论体积计算
    import math
    radius = 2.0
    theoretical_volume = (4/3) * math.pi * radius**3
    print(f"理论体积: {theoretical_volume:.2f}")
    
    # 检查面标签
    face_info = get_face_info(test_sphere)
    print(f"球体有 {face_info['total_faces']} 个面")
    print(f"标签面: {face_info['tagged_faces']}")
else:
    print("球体创建失败")
```

### 参数验证
```python
from simplecadapi import *

# 测试不同参数
valid_spheres = []

# 正常球体
normal_sphere = make_sphere(1.0)
valid_spheres.append(normal_sphere)

# 小球体
tiny_sphere = make_sphere(0.01)
valid_spheres.append(tiny_sphere)

# 大球体
large_sphere = make_sphere(100.0)
valid_spheres.append(large_sphere)

# 无效参数测试
try:
    invalid_sphere = make_sphere(-1.0)  # 负半径
except Exception as e:
    print(f"参数验证成功: {e}")

try:
    zero_sphere = make_sphere(0.0)  # 零半径
except Exception as e:
    print(f"零半径验证: {e}")
```

## 注意事项
- radius必须为正值
- 球体的中心位于当前坐标系的原点
- 球体是完全对称的几何体，所有方向上的尺寸都相等
- 自动添加面标签（通常只有一个"surface"标签，因为球面是连续的）
- 球体计算相对复杂，可能影响性能
- 适用于轴承、装饰、流体建模、科学模拟等应用
- 球体与其他几何体的布尔运算可以创建有趣的形状
- 在精密应用中，球体的精度取决于底层CAD引擎的设置
- 球体没有边和顶点，只有一个连续的曲面
