# fillet 函数文档

## 定义
```python
def fillet(body: Body, edges: List[Line], radius: float) -> Body
```

## 作用
对3D实体的边进行圆角处理，使尖锐的边变成圆滑的过渡。圆角可以改善外观、减少应力集中、便于制造。

## 参数
- `body` (Body): 要进行圆角处理的实体
- `edges` (List[Line]): 要圆角的边列表（当前实现中可以为空列表，会对所有边进行圆角）
- `radius` (float): 圆角半径

## 返回值
- `Body`: 圆角处理后的实体

## 示例代码

### 基础立方体圆角（来自comprehensive_test）
```python
from simplecadapi import *

# 创建立方体并进行圆角
test_cube = make_box(2.0, 2.0, 2.0, center=True)
filleted_cube = fillet(test_cube, [], radius=0.2)
```

### 圆柱体圆角
```python
from simplecadapi import *

# 创建圆柱体并对上下边缘圆角
cylinder = make_cylinder(1.0, 2.0)
filleted_cylinder = fillet(cylinder, [], radius=0.1)
```

### 复杂形状圆角
```python
from simplecadapi import *

# 创建L形拉伸体
l_profile = make_rectangle(3.0, 1.0, center=False)
l_solid = extrude(l_profile, distance=0.5)

# 添加第二部分
with LocalCoordinateSystem(origin=(0, 1.0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    l2_profile = make_rectangle(1.0, 2.0, center=False)
    l2_solid = extrude(l2_profile, distance=0.5)

l_shape = union(l_solid, l2_solid)

# 对整个L形进行圆角
filleted_l = fillet(l_shape, [], radius=0.1)
```

### 机械零件圆角
```python
from simplecadapi import *

# 创建机械支架
base = make_box(4.0, 2.0, 0.5, center=True)

# 添加立柱
with LocalCoordinateSystem(origin=(0, 0, 0.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    column = make_cylinder(0.3, 2.0)

bracket = union(base, column)

# 对连接处进行圆角处理，提高强度
filleted_bracket = fillet(bracket, [], radius=0.15)
```

### 不同圆角半径的应用
```python
from simplecadapi import *

# 创建基础形状
base_shape = make_box(3.0, 2.0, 1.0, center=True)

# 小圆角版本
small_fillet = fillet(base_shape, [], radius=0.05)

# 中等圆角版本  
medium_fillet = fillet(base_shape, [], radius=0.2)

# 大圆角版本
large_fillet = fillet(base_shape, [], radius=0.5)
```

### 电子产品外壳圆角
```python
from simplecadapi import *

# 创建电子设备外壳
case_profile = make_rectangle(10.0, 6.0, center=True)
case_body = extrude(case_profile, distance=2.0)

# 先抽壳
hollow_case = shell(case_body, thickness=0.2, face_tags=["top"])

# 再圆角，创建现代感外观
modern_case = fillet(hollow_case, [], radius=0.3)
```

### 容器圆角设计
```python
from simplecadapi import *

# 创建圆柱形容器
container = make_cylinder(2.0, 3.0)

# 移除顶部形成开口
open_container = shell(container, thickness=0.1, face_tags=["top"])

# 对开口边缘进行圆角，便于使用
comfortable_container = fillet(open_container, [], radius=0.05)
```

### 管道连接件圆角
```python
from simplecadapi import *

# 创建T形管道连接
main_pipe = make_cylinder(0.5, 4.0)

# 旋转坐标系创建侧管
with LocalCoordinateSystem(
    origin=(0, 0, 2.0),
    x_axis=(0, 1, 0),
    y_axis=(1, 0, 0)
):
    side_pipe = make_cylinder(0.4, 2.0)

t_joint = union(main_pipe, side_pipe)

# 对连接处圆角，减少湍流
smooth_t_joint = fillet(t_joint, [], radius=0.1)
```

### 阶梯状结构圆角
```python
from simplecadapi import *

# 创建阶梯状结构
step1 = make_box(4.0, 4.0, 1.0, center=True)

with LocalCoordinateSystem(origin=(0, 0, 1.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    step2 = make_box(3.0, 3.0, 1.0, center=True)

with LocalCoordinateSystem(origin=(0, 0, 2.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    step3 = make_box(2.0, 2.0, 1.0, center=True)

stepped_pyramid = union(step1, step2)
stepped_pyramid = union(stepped_pyramid, step3)

# 圆角处理，创建平滑过渡
smooth_pyramid = fillet(stepped_pyramid, [], radius=0.2)
```

### 齿轮圆角处理
```python
from simplecadapi import *
import math

# 创建简化的齿轮基体
gear_body = make_cylinder(2.0, 0.5)

# 添加齿（简化为小立方体）
gear_with_teeth = gear_body
tooth_size = 0.3

for i in range(12):
    angle = i * 2 * math.pi / 12
    x = 2.2 * math.cos(angle)
    y = 2.2 * math.sin(angle)
    
    with LocalCoordinateSystem(origin=(x, y, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        tooth = make_box(tooth_size, tooth_size, 0.5, center=True)
        gear_with_teeth = union(gear_with_teeth, tooth)

# 对齿轮进行轻微圆角，减少应力集中
smooth_gear = fillet(gear_with_teeth, [], radius=0.02)
```

### 多级圆角处理
```python
from simplecadapi import *

# 创建复杂的连接件
main_block = make_box(3.0, 2.0, 1.0, center=True)

# 添加连接凸起
with LocalCoordinateSystem(origin=(0, 0, 1.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    connector = make_cylinder(0.8, 0.5)

connection = union(main_block, connector)

# 第一次圆角：大圆角处理主要连接
first_fillet = fillet(connection, [], radius=0.3)

# 第二次圆角：小圆角处理细节（注意：实际中需要选择特定边）
# 这里演示概念，实际可能需要更精确的边选择
final_part = fillet(first_fillet, [], radius=0.05)
```

### 圆角失败处理
```python
from simplecadapi import *

# 创建测试形状
test_shape = make_box(1.0, 1.0, 1.0, center=True)

try:
    # 尝试过大的圆角半径
    over_filleted = fillet(test_shape, [], radius=0.8)  # 可能失败
    if over_filleted.is_valid():
        print("圆角操作成功")
    else:
        print("圆角半径过大，操作失败")
except Exception as e:
    print(f"圆角操作异常: {e}")
    # 使用较小的半径重试
    safe_filleted = fillet(test_shape, [], radius=0.2)
```

## 注意事项
- 圆角半径不能超过实体的最小尺寸的一半
- 过大的圆角半径会导致操作失败
- 圆角操作会增加几何复杂性，可能影响后续操作
- 在制造前进行圆角处理可以减少应力集中
- 当前实现对所有边进行圆角，未来版本可能支持选择性圆角
- 适用于改善外观、减少应力、便于制造的场合
- 圆角半径的选择应考虑功能需求和制造工艺
