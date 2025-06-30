# make_box 函数文档

## 定义
```python
def make_box(width: float, height: float, depth: float, center: bool = True) -> Body
```

## 作用
直接创建立方体/长方体3D实体。这是创建基础几何体的便捷函数，自动生成带标签的实体。

## 参数
- `width` (float): 盒子在X方向的宽度
- `height` (float): 盒子在Y方向的高度  
- `depth` (float): 盒子在Z方向的深度
- `center` (bool): 是否以当前坐标系原点为中心，默认为True

## 返回值
- `Body`: 立方体/长方体实体，自动添加面标签

## 示例代码

### 基础立方体创建（来自comprehensive_test）
```python
from simplecadapi import *

# 创建中心对齐的立方体
base_box = make_box(1.0, 1.0, 0.2, center=True)

# 创建线性阵列
linear_array = make_linear_pattern(base_box, direction=(2, 0, 0), count=3, spacing=1.5)
```

### 不同尺寸的盒子
```python
from simplecadapi import *

# 正立方体
cube = make_box(2.0, 2.0, 2.0, center=True)

# 长方体
rectangular_box = make_box(4.0, 2.0, 1.0, center=True)

# 薄板
thin_plate = make_box(5.0, 3.0, 0.1, center=True)

# 长条
beam = make_box(10.0, 0.5, 0.5, center=True)
```

### 原点对齐盒子
```python
from simplecadapi import *

# 以原点为一个角的盒子
corner_box = make_box(3.0, 2.0, 1.0, center=False)
# 角点位置: (0,0,0) 到 (3,2,1)
```

### 在不同坐标系中创建
```python
from simplecadapi import *

# 在局部坐标系中创建盒子
with LocalCoordinateSystem(origin=(5, 3, 2), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    local_box = make_box(2.0, 1.5, 1.0, center=True)
    # 实际位置会根据局部坐标系变换
```

### 建筑结构应用
```python
from simplecadapi import *

# 创建建筑框架
# 底板
foundation = make_box(10.0, 8.0, 0.5, center=True)

# 墙体
with LocalCoordinateSystem(origin=(0, 3.75, 1.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    wall1 = make_box(10.0, 0.5, 3.0, center=True)

with LocalCoordinateSystem(origin=(0, -3.75, 1.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    wall2 = make_box(10.0, 0.5, 3.0, center=True)

# 组装建筑结构
building = union(foundation, wall1)
building = union(building, wall2)
```

### 机械零件基础形状
```python
from simplecadapi import *

# 创建机械底座
machine_base = make_box(8.0, 6.0, 2.0, center=True)

# 添加导轨
with LocalCoordinateSystem(origin=(-3, 0, 2.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    rail1 = make_box(2.0, 6.0, 0.5, center=True)

with LocalCoordinateSystem(origin=(3, 0, 2.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    rail2 = make_box(2.0, 6.0, 0.5, center=True)

machine_frame = union(machine_base, rail1)
machine_frame = union(machine_frame, rail2)
```

### 容器制作
```python
from simplecadapi import *

# 外壳
outer_shell = make_box(6.0, 4.0, 3.0, center=True)

# 内腔（稍小）
inner_cavity = make_box(5.6, 3.6, 2.8, center=True)

# 创建容器
container = cut(outer_shell, inner_cavity)

# 添加盖子
with LocalCoordinateSystem(origin=(0, 0, 1.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    lid = make_box(6.2, 4.2, 0.2, center=True)
```

### 电子设备外壳
```python
from simplecadapi import *

# 主外壳
main_case = make_box(12.0, 8.0, 3.0, center=True)

# 内部隔板
with LocalCoordinateSystem(origin=(0, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    separator = make_box(11.8, 0.2, 2.8, center=True)

# 安装支架
mount_positions = [(-5, -3.5), (5, -3.5), (5, 3.5), (-5, 3.5)]
electronics_housing = union(main_case, separator)

for x, y in mount_positions:
    with LocalCoordinateSystem(origin=(x, y, -1.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        mount = make_box(1.0, 1.0, 0.5, center=True)
        electronics_housing = union(electronics_housing, mount)
```

### 家具制作
```python
from simplecadapi import *

# 桌面
table_top = make_box(120.0, 60.0, 3.0, center=True)

# 桌腿
leg_positions = [(-55, -25), (55, -25), (55, 25), (-55, 25)]
furniture_table = table_top

for x, y in leg_positions:
    with LocalCoordinateSystem(origin=(x, y, -38.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
        leg = make_box(5.0, 5.0, 75.0, center=True)
        furniture_table = union(furniture_table, leg)

# 抽屉
with LocalCoordinateSystem(origin=(0, 20, -10), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    drawer = make_box(40.0, 15.0, 8.0, center=True)
    furniture_table = union(furniture_table, drawer)
```

### 包装盒设计
```python
from simplecadapi import *

# 外盒
package_outer = make_box(15.0, 10.0, 5.0, center=True)

# 内部缓冲层
buffer_thickness = 0.5
inner_size_x = 15.0 - 2 * buffer_thickness
inner_size_y = 10.0 - 2 * buffer_thickness
inner_size_z = 5.0 - buffer_thickness

package_inner = make_box(inner_size_x, inner_size_y, inner_size_z, center=True)

# 创建包装盒
package_box = cut(package_outer, package_inner)

# 添加产品位置（凹槽）
with LocalCoordinateSystem(origin=(0, 0, 1.25), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    product_cavity = make_box(8.0, 6.0, 2.5, center=True)
    custom_package = cut(package_box, product_cavity)
```

### 模块化设计
```python
from simplecadapi import *

# 标准模块单元
standard_module = make_box(5.0, 5.0, 2.0, center=True)

# 连接器模块
with LocalCoordinateSystem(origin=(2.5, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    connector = make_box(1.0, 5.0, 2.0, center=True)

# 基础单元
basic_unit = union(standard_module, connector)

# 创建模块阵列
module_array = make_2d_pattern(
    basic_unit,
    x_direction=(6, 0, 0),
    y_direction=(0, 6, 0),
    x_count=3,
    y_count=2,
    x_spacing=6.0,
    y_spacing=6.0
)
```

### 工具制作
```python
from simplecadapi import *

# 工具手柄
tool_handle = make_box(2.0, 1.5, 15.0, center=True)

# 工具头
with LocalCoordinateSystem(origin=(0, 0, 8.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    tool_head = make_box(4.0, 3.0, 2.0, center=True)

# 组装工具
assembled_tool = union(tool_handle, tool_head)

# 添加握把纹理区域
with LocalCoordinateSystem(origin=(0, 0, -5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    grip_area = make_box(2.2, 1.7, 6.0, center=True)
    tool_with_grip = union(assembled_tool, grip_area)
```

### 测试和验证
```python
from simplecadapi import *

# 创建测试盒子
test_box = make_box(2.0, 3.0, 1.0, center=True)

# 验证盒子属性
if test_box.is_valid():
    print("盒子创建成功")
    
    # 检查面标签（make_box自动添加面标签）
    face_info = get_face_info(test_box)
    print(f"盒子有 {face_info['total_faces']} 个面")
    print(f"标签面: {face_info['tagged_faces']}")
else:
    print("盒子创建失败")
```

## 注意事项
- 所有尺寸参数必须为正值
- center=True时，盒子以当前坐标系原点为中心
- center=False时，盒子的一个角位于当前坐标系原点
- 自动添加面标签："top", "bottom", "front", "back", "left", "right"
- 面标签便于后续的面选择操作（如抽壳时指定开口面）
- 这是最基础的3D几何体，常用作其他复杂形状的基础
- 可以与其他操作组合：布尔运算、圆角、倒角、阵列等
- 适用于建筑、机械、电子、家具等各种设计领域
