# export_step

## 定义
```python
def export_step(body: Body, filename: str)
```

## 作用
将三维实体导出为STEP格式文件。STEP（Standard for the Exchange of Product Data）是一种广泛使用的CAD数据交换标准，支持精确的几何信息和拓扑关系，适用于专业CAD软件之间的数据交换。

**参数说明：**
- `body`: 要导出的三维实体
- `filename`: 导出文件的路径，建议使用 `.step` 或 `.stp` 扩展名

**返回值：**
- 无返回值，直接生成文件

## 示例代码

### 基础STEP导出
```python
from simplecadapi.operations import *

# 创建一个简单的立方体
cube = make_box(20, 20, 20, center=True)

# 导出为STEP文件
export_step(cube, "output/cube.step")
```

### 复杂几何体导出
```python
from simplecadapi.operations import *

# 创建复杂的几何体
base_cylinder = make_cylinder(radius=15, height=30)
top_cylinder = make_cylinder(radius=8, height=10)

# 创建孔
hole = make_cylinder(radius=3, height=35)

# 组合操作
complex_part = union(base_cylinder, top_cylinder)
complex_part = cut(complex_part, hole)

# 导出复杂几何体
export_step(complex_part, "output/complex_part.step")
```

### 导出带布尔操作的模型
```python
from simplecadapi.operations import *

# 创建基础形状
main_box = make_box(40, 30, 15, center=True)

# 创建多个孔
hole1 = make_cylinder(radius=3, height=20)
hole2 = make_cylinder(radius=2, height=20)
hole3 = make_cylinder(radius=2.5, height=20)

# 假设孔在不同位置（实际需要平移操作）
# 这里简化处理
holes = union(hole1, hole2)
holes = union(holes, hole3)

# 从主体中减去孔
part_with_holes = cut(main_box, holes)

# 导出为STEP文件
export_step(part_with_holes, "output/part_with_holes.step")
```

### 导出阵列模型
```python
from simplecadapi.operations import *
import math

# 创建基础单元
unit = make_box(5, 5, 5, center=True)

# 创建线性阵列
linear_array = make_linear_pattern(
    body=unit,
    direction=(1, 0, 0),
    count=5,
    spacing=8
)

# 导出阵列模型
export_step(linear_array, "output/linear_array.step")
```

### 导出旋转扫掠模型
```python
from simplecadapi.operations import *

# 创建L形截面
points = [
    make_point(10, 0, 0),
    make_point(10, 5, 0),
    make_point(2, 5, 0),
    make_point(2, 15, 0),
    make_point(0, 15, 0),
    make_point(0, 0, 0),
    make_point(10, 0, 0)
]

lines = [make_segement(points[i], points[i+1]) 
         for i in range(len(points)-1)]
l_profile = make_sketch(lines)

# 旋转扫掠
revolved_part = revolve(
    sketch=l_profile,
    axis=(0, 0, 1),
    angle=180
)

# 导出旋转体
export_step(revolved_part, "output/revolved_l_profile.step")
```

### 导出齿轮模型
```python
from simplecadapi.operations import *
import math

# 创建齿轮基体
gear_base = make_cylinder(radius=20, height=8)

# 创建简化的齿形
tooth_rect = make_rectangle(2, 4)
tooth = extrude(tooth_rect, 8)

# 创建齿的径向阵列
center_point = make_point(0, 0, 0)
teeth_array = make_radial_pattern(
    body=tooth,
    center=center_point,
    axis=(0, 0, 1),
    count=12,
    angle=2 * math.pi
)

# 合并齿轮
gear = union(gear_base, teeth_array)

# 创建中心孔
center_hole = make_cylinder(radius=5, height=10)
gear_with_hole = cut(gear, center_hole)

# 导出齿轮模型
export_step(gear_with_hole, "output/gear.step")
```

### 批量导出多个模型
```python
from simplecadapi.operations import *

# 创建多个不同的模型
models = {
    "sphere": make_sphere(radius=10),
    "cylinder": make_cylinder(radius=8, height=20),
    "box": make_box(15, 15, 15, center=True)
}

# 批量导出
for name, model in models.items():
    filename = f"output/{name}.step"
    export_step(model, filename)
    print(f"已导出: {filename}")
```

### 导出带倒角的模型
```python
from simplecadapi.operations import *

# 创建基础立方体
base_cube = make_box(30, 30, 30, center=True)

# 获取边（这里简化处理，实际需要选择特定边）
# 假设我们有一种方法获取边
# edges = get_edges(base_cube)

# 创建倒角（这里简化，实际需要edge参数）
# chamfered_cube = chamfer(base_cube, edges, distance=3)

# 由于edge选择复杂，这里用简单模型演示
simple_model = base_cube

# 导出带倒角的模型
export_step(simple_model, "output/chamfered_cube.step")
```

### 导出装配体模型
```python
from simplecadapi.operations import *

# 创建装配体的各个部件
base_plate = make_box(50, 40, 5, center=True)
pillar1 = make_cylinder(radius=3, height=20)
pillar2 = make_cylinder(radius=3, height=20)
pillar3 = make_cylinder(radius=3, height=20)
pillar4 = make_cylinder(radius=3, height=20)

# 合并装配体（实际应用中会有复杂的位置关系）
assembly = union(base_plate, pillar1)
assembly = union(assembly, pillar2)
assembly = union(assembly, pillar3)
assembly = union(assembly, pillar4)

# 导出装配体
export_step(assembly, "output/assembly.step")
```

## 注意事项
1. STEP文件保持高精度的几何信息，文件大小通常比STL大
2. 函数会自动创建必要的目录结构
3. 如果文件已存在，会被覆盖
4. STEP格式适合在不同CAD软件间交换数据
5. 导出的文件可以被SolidWorks、AutoCAD、Fusion 360等专业软件打开
6. 确保实体是有效的（调用 `body.is_valid()`）
7. 建议使用 `.step` 或 `.stp` 文件扩展名
8. 大型复杂模型的导出可能需要较长时间
