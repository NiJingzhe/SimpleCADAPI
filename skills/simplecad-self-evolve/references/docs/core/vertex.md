# Vertex 顶点

## 概述

`Vertex` 是 SimpleCAD API 中的顶点类，表示三维空间中的一个点。它包装了 CADQuery 的 Vertex 对象，并添加了标签功能，用于标识和管理几何体中的特定顶点。

## 类定义

```python
class Vertex(TaggedMixin):
    """顶点类，包装CADQuery的Vertex，添加标签功能"""
```

## 继承关系

- 继承自 `TaggedMixin`，具有标签和元数据功能

## 用途

- 表示三维空间中的点
- 作为边、线、面等几何体的构成元素
- 提供顶点的坐标信息
- 支持标签管理和查询

## 构造函数

### `__init__(cq_vertex)`

初始化顶点对象。

**参数:**
- `cq_vertex` (cadquery.Vertex): CADQuery 的顶点对象

**异常:**
- `ValueError`: 当输入的顶点对象无效时抛出

**示例:**
```python
from simplecadapi import make_point_rvertex

# 通过 SimpleCAD 函数创建顶点
vertex = make_point_rvertex(1.0, 2.0, 3.0)
```

## 主要属性

- `cq_vertex`: 底层的 CADQuery 顶点对象
- `_tags`: 标签集合（继承自 TaggedMixin）
- `_metadata`: 元数据字典（继承自 TaggedMixin）

## 常用方法

### `get_coordinates()`

获取顶点的坐标。

**返回:**
- `Tuple[float, float, float]`: 顶点坐标 (x, y, z)

**异常:**
- `ValueError`: 获取坐标失败时抛出

**示例:**
```python
from simplecadapi import make_point_rvertex

vertex = make_point_rvertex(1.0, 2.0, 3.0)
coords = vertex.get_coordinates()
print(coords)  # (1.0, 2.0, 3.0)
```

### 标签管理方法

继承自 `TaggedMixin` 的方法：

#### `add_tag(tag)`
添加标签。

**示例:**
```python
vertex = make_point_rvertex(0, 0, 0)
vertex.add_tag("origin")
vertex.add_tag("reference_point")
```

#### `has_tag(tag)`
检查是否有指定标签。

**示例:**
```python
vertex = make_point_rvertex(0, 0, 0)
vertex.add_tag("origin")

if vertex.has_tag("origin"):
    print("这是原点")
```

#### `get_tags()`
获取所有标签。

**示例:**
```python
vertex = make_point_rvertex(0, 0, 0)
vertex.add_tag("origin")
vertex.add_tag("reference")

tags = vertex.get_tags()
print(tags)  # {'origin', 'reference'}
```

#### `remove_tag(tag)`
移除标签。

**示例:**
```python
vertex = make_point_rvertex(0, 0, 0)
vertex.add_tag("temp")
vertex.remove_tag("temp")
```

### 元数据管理方法

#### `set_metadata(key, value)`
设置元数据。

**示例:**
```python
vertex = make_point_rvertex(0, 0, 0)
vertex.set_metadata("created_by", "user_input")
vertex.set_metadata("importance", "high")
```

#### `get_metadata(key, default=None)`
获取元数据。

**示例:**
```python
vertex = make_point_rvertex(0, 0, 0)
vertex.set_metadata("created_by", "user_input")

creator = vertex.get_metadata("created_by")
print(creator)  # "user_input"

unknown = vertex.get_metadata("unknown_key", "default_value")
print(unknown)  # "default_value"
```

## 使用示例

### 创建和使用顶点

```python
from simplecadapi import make_point_rvertex

# 创建顶点
vertex1 = make_point_rvertex(0, 0, 0)
vertex2 = make_point_rvertex(1, 1, 1)

# 获取坐标
coords1 = vertex1.get_coordinates()
coords2 = vertex2.get_coordinates()

print(f"顶点1坐标: {coords1}")  # 顶点1坐标: (0.0, 0.0, 0.0)
print(f"顶点2坐标: {coords2}")  # 顶点2坐标: (1.0, 1.0, 1.0)
```

### 顶点标签管理

```python
from simplecadapi import make_point_rvertex

# 创建关键点
origin = make_point_rvertex(0, 0, 0)
corner1 = make_point_rvertex(10, 0, 0)
corner2 = make_point_rvertex(10, 10, 0)
corner3 = make_point_rvertex(0, 10, 0)

# 添加标签
origin.add_tag("origin")
origin.add_tag("reference")

corner1.add_tag("corner")
corner1.add_tag("x_axis")

corner2.add_tag("corner")
corner2.add_tag("diagonal")

corner3.add_tag("corner")
corner3.add_tag("y_axis")

# 查找所有角点
vertices = [origin, corner1, corner2, corner3]
corners = [v for v in vertices if v.has_tag("corner")]

print(f"找到 {len(corners)} 个角点")
```

### 顶点分类和管理

```python
from simplecadapi import make_point_rvertex

def create_grid_vertices(width, height, spacing):
    """创建网格顶点"""
    vertices = []
    
    for i in range(width + 1):
        for j in range(height + 1):
            x = i * spacing
            y = j * spacing
            z = 0
            
            vertex = make_point_rvertex(x, y, z)
            
            # 添加位置标签
            if i == 0 and j == 0:
                vertex.add_tag("origin")
            elif i == 0:
                vertex.add_tag("left_edge")
            elif i == width:
                vertex.add_tag("right_edge")
            
            if j == 0:
                vertex.add_tag("bottom_edge")
            elif j == height:
                vertex.add_tag("top_edge")
            
            # 添加角点标签
            if (i == 0 or i == width) and (j == 0 or j == height):
                vertex.add_tag("corner")
            
            # 添加元数据
            vertex.set_metadata("grid_position", (i, j))
            vertex.set_metadata("distance_from_origin", (x*x + y*y)**0.5)
            
            vertices.append(vertex)
    
    return vertices

# 创建 5x3 网格
vertices = create_grid_vertices(5, 3, 1.0)

# 查找特定顶点
corners = [v for v in vertices if v.has_tag("corner")]
origin = [v for v in vertices if v.has_tag("origin")][0]

print(f"网格顶点总数: {len(vertices)}")
print(f"角点数量: {len(corners)}")
print(f"原点坐标: {origin.get_coordinates()}")
```

### 顶点距离计算

```python
import math
from simplecadapi import make_point_rvertex

def calculate_distance(vertex1, vertex2):
    """计算两个顶点之间的距离"""
    coords1 = vertex1.get_coordinates()
    coords2 = vertex2.get_coordinates()
    
    dx = coords2[0] - coords1[0]
    dy = coords2[1] - coords1[1]
    dz = coords2[2] - coords1[2]
    
    return math.sqrt(dx*dx + dy*dy + dz*dz)

# 创建顶点
v1 = make_point_rvertex(0, 0, 0)
v2 = make_point_rvertex(3, 4, 0)
v3 = make_point_rvertex(0, 0, 5)

# 计算距离
dist12 = calculate_distance(v1, v2)
dist13 = calculate_distance(v1, v3)
dist23 = calculate_distance(v2, v3)

print(f"v1 到 v2 的距离: {dist12}")  # 5.0
print(f"v1 到 v3 的距离: {dist13}")  # 5.0
print(f"v2 到 v3 的距离: {dist23}")  # 约 7.07
```

## 字符串表示

```python
from simplecadapi import make_point_rvertex

vertex = make_point_rvertex(1.234, 5.678, 9.012)
vertex.add_tag("test_point")
vertex.set_metadata("created_by", "example")

print(vertex)
```

输出：
```
Vertex:
  coordinates: [1.234, 5.678, 9.012]
  tags: [test_point]
  metadata:
    created_by: example
```

## 与其他几何体的关系

顶点是构成更复杂几何体的基本元素：

- **边 (Edge)**: 由两个顶点定义
- **线 (Wire)**: 由多个连接的边组成，包含多个顶点
- **面 (Face)**: 边界由顶点定义
- **实体 (Solid)**: 最终由顶点构成

## 注意事项

- 顶点对象包装了 CADQuery 的底层顶点，不要直接修改坐标
- 标签是字符串类型，区分大小写
- 元数据可以存储任意类型的值
- 顶点坐标是只读的，如需修改位置应创建新顶点
- 浮点数坐标可能存在精度问题，比较时应考虑容差
