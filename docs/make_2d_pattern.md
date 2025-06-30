# make_2d_pattern

## 定义
```python
def make_2d_pattern(body: Body, 
               x_direction: Tuple[float, float, float], 
               y_direction: Tuple[float, float, float],
               x_count: int, 
               y_count: int,
               x_spacing: float, 
               y_spacing: float) -> Body
```

## 作用
创建实体的二维矩形阵列。该函数将输入实体沿两个指定方向创建网格状的阵列，可以创建复杂的重复几何结构，如孔阵列、螺栓模式、散热片等。

**参数说明：**
- `body`: 要阵列的源实体
- `x_direction`: X方向的向量 (x, y, z)
- `y_direction`: Y方向的向量 (x, y, z)
- `x_count`: X方向的阵列数量
- `y_count`: Y方向的阵列数量
- `x_spacing`: X方向的间距
- `y_spacing`: Y方向的间距

**返回值：**
- 返回包含所有阵列实体的 Body 对象

## 示例代码

### 基础矩形阵列
```python
from simplecadapi.operations import *

# 创建基础圆柱体作为螺栓孔
bolt_hole = make_cylinder(radius=2, height=10)

# 创建4x3的矩形阵列
rect_array = make_2d_pattern(
    body=bolt_hole,
    x_direction=(1, 0, 0),  # X轴方向
    y_direction=(0, 1, 0),  # Y轴方向
    x_count=4,              # X方向4个
    y_count=3,              # Y方向3个
    x_spacing=20,           # X间距20
    y_spacing=15            # Y间距15
)

export_stl(rect_array, "output/2d_array_rectangular.stl")
```

### 复杂形状的2D阵列
```python
from simplecadapi.operations import *

# 创建复杂的基础形状
base_rect = make_rectangle(6, 4)
base_body = extrude(base_rect, 8)

# 添加顶部圆柱
top_circle = make_circle(2)
top_cylinder = extrude(top_circle, 4)
top_cylinder = top_cylinder  # 假设有平移到顶部的操作

# 合并形状
complex_shape = union(base_body, top_cylinder)

# 创建2D阵列
complex_2d_array = make_2d_pattern(
    body=complex_shape,
    x_direction=(1, 0, 0),
    y_direction=(0, 1, 0),
    x_count=3,
    y_count=2,
    x_spacing=25,
    y_spacing=30
)

export_stl(complex_2d_array, "output/2d_array_complex.stl")
```

### 斜向2D阵列
```python
from simplecadapi.operations import *

# 创建小立方体
cube = make_box(4, 4, 4, center=True)

# 创建斜向2D阵列
diagonal_2d_array = make_2d_pattern(
    body=cube,
    x_direction=(1, 0.5, 0),    # 带倾斜的X方向
    y_direction=(0, 1, 0),      # 标准Y方向
    x_count=5,
    y_count=3,
    x_spacing=12,
    y_spacing=12
)

export_stl(diagonal_2d_array, "output/2d_array_diagonal.stl")
```

### 散热片模式
```python
from simplecadapi.operations import *

# 创建散热片单元
fin_rect = make_rectangle(2, 8)
fin = extrude(fin_rect, 15)

# 创建散热片阵列
heat_sink = make_2d_pattern(
    body=fin,
    x_direction=(1, 0, 0),
    y_direction=(0, 1, 0),
    x_count=10,     # 10片散热片
    y_count=1,      # 单排
    x_spacing=3,    # 间距3单位
    y_spacing=0
)

export_stl(heat_sink, "output/heat_sink_array.stl")
```

### 孔阵列模式
```python
from simplecadapi.operations import *

# 创建基础板
base_plate = make_box(100, 80, 5, center=True)

# 创建孔
hole = make_cylinder(radius=3, height=8)

# 创建孔阵列
holes_array = make_2d_pattern(
    body=hole,
    x_direction=(1, 0, 0),
    y_direction=(0, 1, 0),
    x_count=8,      # 8x6的孔阵列
    y_count=6,
    x_spacing=12,
    y_spacing=12
)

# 从基础板中减去孔阵列
perforated_plate = cut(base_plate, holes_array)
export_stl(perforated_plate, "output/perforated_plate.stl")
```

### 3D空间2D阵列
```python
from simplecadapi.operations import *

# 创建球体
sphere = make_sphere(radius=2)

# 在XZ平面创建2D阵列
xz_array = make_2d_pattern(
    body=sphere,
    x_direction=(1, 0, 0),      # X方向
    y_direction=(0, 0, 1),      # Z方向
    x_count=4,
    y_count=3,
    x_spacing=8,
    y_spacing=8
)

export_stl(xz_array, "output/2d_array_xz_plane.stl")
```

### 密集阵列
```python
from simplecadapi.operations import *

# 创建小圆柱
small_cylinder = make_cylinder(radius=1, height=5)

# 创建密集阵列
dense_array = make_2d_pattern(
    body=small_cylinder,
    x_direction=(1, 0, 0),
    y_direction=(0, 1, 0),
    x_count=12,     # 12x8的密集阵列
    y_count=8,
    x_spacing=4,    # 紧密间距
    y_spacing=4
)

export_stl(dense_array, "output/dense_2d_array.stl")
```

## 注意事项
1. 两个方向向量不必垂直，可以创建平行四边形阵列
2. `x_count` 和 `y_count` 都必须大于等于1
3. 总的实体数量为 `x_count × y_count`
4. 间距是相邻实体中心之间的距离
5. 方向向量会影响阵列的最终形状和方向
6. 大型阵列可能会消耗较多内存和计算时间
7. 函数返回包含所有阵列实体的单一 Body 对象
