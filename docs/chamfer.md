# chamfer 函数文档

## 定义
```python
def chamfer(body: Body, edges: List[Line], distance: float) -> Body
```

## 作用
对3D实体的边进行倒角处理，将尖锐的边切除成斜面。倒角比圆角更易于制造，常用于机械零件的边缘处理。

## 参数
- `body` (Body): 要进行倒角处理的实体
- `edges` (List[Line]): 要倒角的边列表（当前实现中可以为空列表，会对所有边进行倒角）
- `distance` (float): 倒角距离

## 返回值
- `Body`: 倒角处理后的实体

## 示例代码

### 基础立方体倒角（来自comprehensive_test）
```python
from simplecadapi import *

# 创建立方体并进行倒角
test_cube = make_box(2.0, 2.0, 2.0, center=True)
chamfered_cube = chamfer(test_cube, [], distance=0.15)
```

### 圆柱体倒角
```python
from simplecadapi import *

# 创建圆柱体并对上下边缘倒角
cylinder = make_cylinder(1.0, 2.0)
chamfered_cylinder = chamfer(cylinder, [], distance=0.1)
```

### 机械零件倒角
```python
from simplecadapi import *

# 创建机械支撑件
support_base = make_box(5.0, 3.0, 1.0, center=True)

# 添加支撑柱
with LocalCoordinateSystem(origin=(0, 0, 1.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    support_column = make_box(2.0, 1.5, 3.0, center=True)

support_assembly = union(support_base, support_column)

# 倒角处理，便于加工和安全
machined_support = chamfer(support_assembly, [], distance=0.2)
```

### 工具头倒角
```python
from simplecadapi import *

# 创建切削工具头基本形状
tool_body = make_cylinder(1.0, 3.0)

# 添加锥形头部
with LocalCoordinateSystem(origin=(0, 0, 3.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    tip_circle = make_circle(1.0)
    point_circle = make_circle(0.1)
    
    with LocalCoordinateSystem(origin=(0, 0, 1.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        tip_cone = loft([tip_circle, point_circle])

cutting_tool = union(tool_body, tip_cone)

# 倒角处理，防止崩刃
safe_tool = chamfer(cutting_tool, [], distance=0.05)
```

### 电子外壳倒角
```python
from simplecadapi import *

# 创建电子设备外壳
enclosure_profile = make_rectangle(8.0, 6.0, center=True)
enclosure_body = extrude(enclosure_profile, distance=3.0)

# 先抽壳形成外壳
hollow_enclosure = shell(enclosure_body, thickness=0.3, face_tags=["top"])

# 倒角处理，安全和美观
safe_enclosure = chamfer(hollow_enclosure, [], distance=0.1)
```

### 结构件倒角
```python
from simplecadapi import *

# 创建结构连接件
main_beam = make_box(6.0, 1.0, 1.0, center=True)

# 添加连接板
with LocalCoordinateSystem(origin=(2.5, 0, 0), x_axis=(0, 1, 0), y_axis=(0, 0, 1)):
    connection_plate = make_box(2.0, 2.0, 0.2, center=True)

structural_joint = union(main_beam, connection_plate)

# 倒角处理，减少应力集中
stress_relieved_joint = chamfer(structural_joint, [], distance=0.1)
```

### 不同倒角尺寸比较
```python
from simplecadapi import *

# 创建基础形状
base_block = make_box(3.0, 2.0, 1.0, center=True)

# 小倒角版本
small_chamfer = chamfer(base_block, [], distance=0.05)

# 中等倒角版本
medium_chamfer = chamfer(base_block, [], distance=0.15)

# 大倒角版本
large_chamfer = chamfer(base_block, [], distance=0.3)
```

### 容器边缘倒角
```python
from simplecadapi import *

# 创建容器
container_cylinder = make_cylinder(2.0, 3.0)

# 抽壳形成开口容器
open_container = shell(container_cylinder, thickness=0.1, face_tags=["top"])

# 对开口边缘倒角，防止割手
safe_container = chamfer(open_container, [], distance=0.08)
```

### 齿轮倒角
```python
from simplecadapi import *
import math

# 创建简化齿轮
gear_base = make_cylinder(2.5, 0.8)

# 添加中心孔
center_hole = make_cylinder(0.5, 1.0)
gear_with_hole = cut(gear_base, center_hole)

# 添加键槽
with LocalCoordinateSystem(origin=(0, 0.4, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    keyway = make_box(0.2, 0.8, 1.0, center=True)

gear_with_keyway = cut(gear_with_hole, keyway)

# 倒角处理，便于装配
finished_gear = chamfer(gear_with_keyway, [], distance=0.05)
```

### 管道连接倒角
```python
from simplecadapi import *

# 创建管道法兰
flange_body = make_cylinder(3.0, 0.5)

# 添加中心孔
center_bore = make_cylinder(1.0, 0.6)
flange_with_bore = cut(flange_body, center_bore)

# 添加螺栓孔
import math
flange_with_holes = flange_with_bore

for i in range(6):
    angle = i * 2 * math.pi / 6
    x = 2.0 * math.cos(angle)
    y = 2.0 * math.sin(angle)
    
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        bolt_hole = make_cylinder(0.2, 0.6)
        flange_with_holes = cut(flange_with_holes, bolt_hole)

# 倒角处理，便于装配和密封
finished_flange = chamfer(flange_with_holes, [], distance=0.1)
```

### 刀具倒角
```python
from simplecadapi import *

# 创建简单的刀片形状
blade_profile = make_rectangle(4.0, 0.2, center=True)
blade_body = extrude(blade_profile, distance=1.0)

# 创建锋利边缘（斜面）
with LocalCoordinateSystem(origin=(2.0, 0, 0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    cutting_edge = make_triangle(
        make_point(0, -0.1, -0.5),
        make_point(0, 0.1, -0.5),
        make_point(0.5, 0, 0)
    )
    edge_solid = extrude(cutting_edge, distance=1.0)

blade_with_edge = union(blade_body, edge_solid)

# 对非切削边缘倒角，安全处理
safe_blade = chamfer(blade_with_edge, [], distance=0.02)
```

### 多阶倒角
```python
from simplecadapi import *

# 创建阶梯状零件
step1 = make_box(4.0, 4.0, 1.0, center=True)

with LocalCoordinateSystem(origin=(0, 0, 1.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    step2 = make_box(3.0, 3.0, 1.0, center=True)

stepped_part = union(step1, step2)

# 第一次大倒角
first_chamfer = chamfer(stepped_part, [], distance=0.2)

# 第二次小倒角（概念演示，实际中需要选择特定边）
refined_part = chamfer(first_chamfer, [], distance=0.05)
```

### 倒角质量检查
```python
from simplecadapi import *

# 创建测试零件
test_part = make_box(2.0, 2.0, 2.0, center=True)

try:
    # 尝试倒角
    chamfered_part = chamfer(test_part, [], distance=0.2)
    
    if chamfered_part.is_valid():
        print("倒角操作成功")
        # 可以进行后续操作
    else:
        print("倒角操作失败，检查参数")
        
except Exception as e:
    print(f"倒角操作异常: {e}")
    # 使用更小的倒角距离重试
    safe_chamfered = chamfer(test_part, [], distance=0.1)
```

## 注意事项
- 倒角距离不能超过实体边缘尺寸的一半
- 倒角比圆角更容易制造，特别是在机械加工中
- 倒角会在原来的尖角处创建斜面
- 过大的倒角距离可能导致操作失败
- 当前实现对所有边进行倒角，未来可能支持选择性倒角
- 适用于机械零件、工具、安全边缘处理
- 倒角常用于去除毛刺、便于装配、提高安全性
- 在技术图纸中通常标注为C0.1（表示0.1的倒角）
