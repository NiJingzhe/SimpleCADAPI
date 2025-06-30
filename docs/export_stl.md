# export_stl

## 定义
```python
def export_stl(body: Body, filename: str, tolerance: float = 0.1)
```

## 作用
将三维实体导出为STL格式文件。STL（Stereolithography）是一种广泛使用的三角网格文件格式，主要用于3D打印、快速原型制作和三维可视化。

**参数说明：**
- `body`: 要导出的三维实体
- `filename`: 导出文件的路径，建议使用 `.stl` 扩展名
- `tolerance`: 网格精度，数值越小精度越高，默认0.1

**返回值：**
- 无返回值，直接生成文件

## 示例代码

### 基础STL导出
```python
from simplecadapi.operations import *

# 创建一个简单的立方体
cube = make_box(20, 20, 20, center=True)

# 导出为STL文件（使用默认精度）
export_stl(cube, "output/cube.stl")
```

### 高精度导出
```python
from simplecadapi.operations import *

# 创建球体
sphere = make_sphere(radius=15)

# 导出高精度STL文件
export_stl(sphere, "output/sphere_high_quality.stl", tolerance=0.01)

# 导出低精度STL文件（适用于快速预览）
export_stl(sphere, "output/sphere_low_quality.stl", tolerance=0.5)
```

### 复杂几何体导出
```python
from simplecadapi.operations import *

# 创建复杂的几何体
base_cylinder = make_cylinder(radius=12, height=25)
top_sphere = make_sphere(radius=8)

# 组合操作
complex_part = union(base_cylinder, top_sphere)

# 创建孔
hole = make_cylinder(radius=3, height=30)
complex_part = cut(complex_part, hole)

# 导出复杂几何体
export_stl(complex_part, "output/complex_part.stl", tolerance=0.05)
```

### 3D打印模型导出
```python
from simplecadapi.operations import *

# 创建适合3D打印的模型
print_model = make_box(40, 30, 5, center=True)

# 添加支撑结构（简化示例）
support1 = make_cylinder(radius=1, height=5)
support2 = make_cylinder(radius=1, height=5)

# 合并支撑
model_with_supports = union(print_model, support1)
model_with_supports = union(model_with_supports, support2)

# 导出3D打印模型（中等精度，平衡质量和文件大小）
export_stl(model_with_supports, "output/3d_print_model.stl", tolerance=0.1)
```

### 阵列模型导出
```python
from simplecadapi.operations import *
import math

# 创建基础单元
unit = make_cylinder(radius=3, height=10)

# 创建径向阵列
center_point = make_point(0, 0, 0)
radial_array = make_radial_pattern(
    body=unit,
    center=center_point,
    axis=(0, 0, 1),
    count=8,
    angle=2 * math.pi
)

# 导出阵列模型
export_stl(radial_array, "output/radial_array.stl", tolerance=0.08)
```

### 螺旋扫掠模型导出
```python
from simplecadapi.operations import *

# 创建小圆形截面
circle_profile = make_circle(radius=2)

# 创建螺旋扫掠
spiral = helical_sweep(
    profile=circle_profile,
    coil_radius=10,
    pitch=5,
    turns=3,
    points_per_turn=16
)

# 导出螺旋模型
export_stl(spiral, "output/spiral.stl", tolerance=0.05)
```

### 不同精度对比导出
```python
from simplecadapi.operations import *

# 创建测试模型
test_sphere = make_sphere(radius=10)

# 导出不同精度的版本
tolerances = {
    "ultra_high": 0.001,    # 超高精度（文件很大）
    "high": 0.01,          # 高精度
    "medium": 0.1,         # 中等精度（推荐）
    "low": 0.5,            # 低精度（快速预览）
    "very_low": 1.0        # 很低精度
}

for quality, tol in tolerances.items():
    filename = f"output/sphere_{quality}.stl"
    export_stl(test_sphere, filename, tolerance=tol)
    print(f"已导出 {quality} 精度: {filename}")
```

### 齿轮3D打印模型
```python
from simplecadapi.operations import *
import math

# 创建3D打印友好的齿轮
gear_base = make_cylinder(radius=18, height=6)

# 创建齿（简化形状，适合3D打印）
tooth_rect = make_rectangle(1.5, 3)
tooth = extrude(tooth_rect, 6)

# 创建齿阵列
center_point = make_point(0, 0, 0)
teeth = make_radial_pattern(
    body=tooth,
    center=center_point,
    axis=(0, 0, 1),
    count=16,
    angle=2 * math.pi
)

# 合并齿轮
gear = union(gear_base, teeth)

# 创建中心孔
center_hole = make_cylinder(radius=4, height=8)
printable_gear = cut(gear, center_hole)

# 导出3D打印齿轮（适中精度）
export_stl(printable_gear, "output/printable_gear.stl", tolerance=0.1)
```

### 批量导出不同格式
```python
from simplecadapi.operations import *

# 创建模型
model = make_box(25, 25, 25, center=True)
hole = make_cylinder(radius=5, height=30)
model_with_hole = cut(model, hole)

# 导出不同用途的STL文件
export_configs = {
    "preview": {"tolerance": 0.5, "suffix": "_preview"},
    "standard": {"tolerance": 0.1, "suffix": "_standard"},
    "high_quality": {"tolerance": 0.02, "suffix": "_hq"},
    "printing": {"tolerance": 0.08, "suffix": "_print"}
}

for config_name, config in export_configs.items():
    filename = f"output/model{config['suffix']}.stl"
    export_stl(model_with_hole, filename, tolerance=config['tolerance'])
```

### 微型零件高精度导出
```python
from simplecadapi.operations import *

# 创建微型精密零件
micro_base = make_box(5, 5, 2, center=True)
micro_hole = make_cylinder(radius=0.5, height=3)
micro_part = cut(micro_base, micro_hole)

# 高精度导出微型零件
export_stl(micro_part, "output/micro_part.stl", tolerance=0.005)
```

### 大型模型优化导出
```python
from simplecadapi.operations import *

# 创建大型复杂模型
large_base = make_box(100, 80, 20, center=True)

# 添加多个特征
features = []
for i in range(10):
    feature = make_cylinder(radius=2, height=25)
    features.append(feature)

# 合并所有特征（简化处理）
large_model = large_base
for feature in features:
    large_model = union(large_model, feature)

# 优化导出（平衡质量和性能）
export_stl(large_model, "output/large_model.stl", tolerance=0.2)
```

## 注意事项
1. `tolerance` 参数控制网格密度：
   - 0.001-0.01: 超高精度，文件大，适合精密零件
   - 0.01-0.1: 高精度，适合大多数应用
   - 0.1-0.5: 中等精度，平衡质量和文件大小
   - 0.5-2.0: 低精度，适合快速预览
2. 函数会自动创建必要的目录结构
3. STL文件只包含三角网格，不保留CAD特征信息
4. 曲面模型（如球体、圆柱）的精度受tolerance影响很大
5. 3D打印通常使用0.05-0.15的tolerance值
6. 文件大小与精度成反比关系
7. 确保实体是有效的闭合几何体
8. 复杂模型的导出可能需要较长时间
