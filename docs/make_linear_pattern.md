# make_linear_pattern

## 定义
```python
def make_linear_pattern(body: Body, 
                   direction: Tuple[float, float, float], 
                   count: int, 
                   spacing: float) -> Body
```

## 作用
创建实体的线性阵列。该函数将输入实体沿指定方向复制多个实例，每个实例之间保持指定的间距。线性阵列常用于创建重复的几何结构，如孔阵列、支柱阵列等。

**参数说明：**
- `body`: 要阵列的源实体
- `direction`: 阵列方向向量 (x, y, z)，会自动标准化
- `count`: 阵列总数量（包括原始实体）
- `spacing`: 实体间距（沿方向向量的距离）

**返回值：**
- 返回包含所有阵列实体的 Body 对象

## 示例代码

### 基础线性阵列
```python
from simplecadapi.operations import *

# 创建基础立方体
base_cube = make_box(10, 10, 10, center=True)

# 沿X轴创建5个立方体的线性阵列，间距为15
linear_array = make_linear_pattern(
    body=base_cube,
    direction=(1, 0, 0),    # X轴方向
    count=5,                # 总共5个实体
    spacing=15              # 间距15单位
)

export_stl(linear_array, "output/linear_array_x.stl")
```

### 不同方向的线性阵列
```python
from simplecadapi.operations import *

# 创建基础圆柱体
cylinder = make_cylinder(radius=5, height=20)

# 沿Y轴方向阵列
y_array = make_linear_pattern(
    body=cylinder,
    direction=(0, 1, 0),    # Y轴方向
    count=4,
    spacing=25
)

# 沿Z轴方向阵列
z_array = make_linear_pattern(
    body=cylinder,
    direction=(0, 0, 1),    # Z轴方向
    count=3,
    spacing=30
)

export_stl(y_array, "output/linear_array_y.stl")
export_stl(z_array, "output/linear_array_z.stl")
```

### 对角方向线性阵列
```python
from simplecadapi.operations import *

# 创建小立方体
small_cube = make_box(5, 5, 5, center=True)

# 沿对角线方向创建阵列
diagonal_array = make_linear_pattern(
    body=small_cube,
    direction=(1, 1, 0),    # XY平面对角线方向
    count=6,
    spacing=12
)

export_stl(diagonal_array, "output/linear_array_diagonal.stl")
```

### 复杂形状的线性阵列
```python
from simplecadapi.operations import *

# 创建复杂的基础形状
base_rect = make_rectangle(8, 4)
base_body = extrude(base_rect, 6)

# 创建孔
hole_circle = make_circle(1.5)
hole_body = extrude(hole_circle, 8)

# 创建带孔的基础形状
complex_shape = cut(base_body, hole_body)

# 创建线性阵列
complex_array = make_linear_pattern(
    body=complex_shape,
    direction=(1, 0, 0),
    count=4,
    spacing=20
)

export_stl(complex_array, "output/complex_linear_array.stl")
```

### 3D方向线性阵列
```python
from simplecadapi.operations import *
import math

# 创建球体
sphere = make_sphere(radius=3)

# 沿3D方向创建阵列
direction_3d = (1, 1, 1)  # 空间对角线方向
array_3d = make_linear_pattern(
    body=sphere,
    direction=direction_3d,
    count=5,
    spacing=10
)

export_stl(array_3d, "output/linear_array_3d.stl")
```

## 注意事项
1. `direction` 向量会被自动标准化，因此 `(1, 0, 0)` 和 `(2, 0, 0)` 效果相同
2. `count` 必须大于等于1，当为1时返回原始实体
3. `spacing` 是相邻实体中心之间的距离
4. 阵列操作会保持原始实体的所有特征和标签
5. 如果实体过于复杂或间距过小，可能导致阵列实体重叠
6. 函数返回的是包含所有阵列实体的单一 Body 对象
