# Face 面

## 概述

`Face` 是 SimpleCAD API 中的面类，表示二维表面几何。面由一个或多个线（Wire）围成，包括外边界和可能的内边界（孔）。它包装了 CADQuery 的 Face 对象，并添加了标签功能。

## 类定义

```python
class Face(TaggedMixin):
    """面类，包装CADQuery的Face，添加标签功能"""
```

## 继承关系

- 继承自 `TaggedMixin`，具有标签和元数据功能

## 用途

- 表示二维表面区域
- 构成实体 (Solid) 的边界
- 定义扫描、拉伸等操作的截面
- 计算面积、法向量等几何属性

## 构造函数

### `__init__(cq_face)`

初始化面对象。

**参数:**
- `cq_face` (cadquery.Face): CADQuery 的面对象

**异常:**
- `ValueError`: 当输入的面对象无效时抛出

**示例:**
```python
from simplecadapi import (
    make_rectangle_rface,
    make_circle_rface,
    make_face_from_wire_rface,
    make_rectangle_rwire
)

# 通过 SimpleCAD 函数创建面
rectangle = make_rectangle_rface(width=5, height=3)
circle = make_circle_rface(center=(0, 0, 0), radius=2.0)

# 从线创建面
wire = make_rectangle_rwire(width=4, height=4)
face_from_wire = make_face_from_wire_rface(wire)
```

## 主要属性

- `cq_face`: 底层的 CADQuery 面对象
- `_tags`: 标签集合（继承自 TaggedMixin）
- `_metadata`: 元数据字典（继承自 TaggedMixin）

## 常用方法

### `get_area()`

获取面的面积。

**返回:**
- `float`: 面的面积

**异常:**
- `ValueError`: 获取面积失败时抛出

**示例:**
```python
from simplecadapi import make_rectangle_rface, make_circle_rface
import math

# 矩形面
rectangle = make_rectangle_rface(width=5, height=3)
rect_area = rectangle.get_area()
print(f"矩形面积: {rect_area}")  # 15.0

# 圆形面
circle = make_circle_rface(center=(0, 0, 0), radius=2.0)
circle_area = circle.get_area()
expected_area = math.pi * 2.0 * 2.0
print(f"圆形面积: {circle_area:.3f}, 期望: {expected_area:.3f}")
```

### `get_normal_at(u, v)`

获取面在指定参数位置的法向量。

**参数:**
- `u` (float, 可选): U 参数，默认 0.5
- `v` (float, 可选): V 参数，默认 0.5

**返回:**
- `cadquery.Vector`: 法向量

**异常:**
- `ValueError`: 获取法向量失败时抛出

**示例:**
```python
from simplecadapi import make_rectangle_rface

rectangle = make_rectangle_rface(width=5, height=3)
normal = rectangle.get_normal_at()
print(f"法向量: ({normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f})")
```

### `get_outer_wire()`

获取面的外边界线。

**返回:**
- `Wire`: 外边界线对象

**异常:**
- `ValueError`: 获取外边界线失败时抛出

**示例:**
```python
from simplecadapi import make_rectangle_rface

rectangle = make_rectangle_rface(width=5, height=3)
outer_wire = rectangle.get_outer_wire()
edges = outer_wire.get_edges()
print(f"外边界由 {len(edges)} 条边组成")
```

### 标签管理方法

继承自 `TaggedMixin` 的方法：

#### `add_tag(tag)`、`has_tag(tag)`、`get_tags()`、`remove_tag(tag)`
#### `set_metadata(key, value)`、`get_metadata(key, default=None)`

使用方法与 Vertex 类似，详见 [Vertex 文档](vertex.md)。

## 使用示例

### 创建不同类型的面

```python
from simplecadapi import (
    make_rectangle_rface,
    make_circle_rface,
    make_face_from_wire_rface,
    make_polyline_rwire
)

# 矩形面
rectangle = make_rectangle_rface(width=10, height=6)
rectangle.add_tag("rectangle")
rectangle.add_tag("quadrilateral")

# 圆形面
circle = make_circle_rface(center=(0, 0, 0), radius=3.0)
circle.add_tag("circle")
circle.add_tag("curved")

# 复杂多边形面
points = [
    (0, 0, 0), (4, 0, 0), (4, 3, 0), (2, 5, 0), (0, 3, 0), (0, 0, 0)
]
polygon_wire = make_polyline_rwire(points=points)
polygon = make_face_from_wire_rface(polygon_wire)
polygon.add_tag("polygon")
polygon.add_tag("complex")

# 分析面的属性
faces = [rectangle, circle, polygon]
for face in faces:
    area = face.get_area()
    normal = face.get_normal_at()
    outer_wire = face.get_outer_wire()
    edges = outer_wire.get_edges()
    tags = face.get_tags()
    
    print(f"面类型: {tags}")
    print(f"  面积: {area:.3f}")
    print(f"  法向量: ({normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f})")
    print(f"  边数: {len(edges)}")
    print()
```

### 面的几何分析

```python
from simplecadapi import make_rectangle_rface, make_circle_rface
import math

def analyze_face_geometry():
    """分析面的几何属性"""
    
    # 创建不同尺寸的矩形
    rectangles = [
        make_rectangle_rface(width=2, height=3),
        make_rectangle_rface(width=4, height=4),
        make_rectangle_rface(width=6, height=2)
    ]
    
    # 创建不同半径的圆
    circles = [
        make_circle_rface(center=(0, 0, 0), radius=1.0),
        make_circle_rface(center=(0, 0, 0), radius=2.0),
        make_circle_rface(center=(0, 0, 0), radius=3.0)
    ]
    
    # 分析矩形
    for i, rect in enumerate(rectangles):
        area = rect.get_area()
        outer_wire = rect.get_outer_wire()
        edges = outer_wire.get_edges()
        
        # 计算周长
        perimeter = sum(edge.get_length() for edge in edges)
        
        # 计算长宽比
        lengths = [edge.get_length() for edge in edges]
        lengths.sort()
        aspect_ratio = lengths[1] / lengths[0] if lengths[0] > 0 else 1.0
        
        rect.add_tag(f"rectangle_{i}")
        rect.set_metadata("area", area)
        rect.set_metadata("perimeter", perimeter)
        rect.set_metadata("aspect_ratio", aspect_ratio)
        
        if aspect_ratio == 1.0:
            rect.add_tag("square")
        elif aspect_ratio > 2.0:
            rect.add_tag("elongated")
        
        print(f"矩形 {i}: 面积={area:.3f}, 周长={perimeter:.3f}, 长宽比={aspect_ratio:.3f}")
    
    # 分析圆形
    for i, circle in enumerate(circles):
        area = circle.get_area()
        outer_wire = circle.get_outer_wire()
        edges = outer_wire.get_edges()
        
        # 计算周长（圆周长）
        perimeter = sum(edge.get_length() for edge in edges)
        
        # 从面积计算半径
        radius_from_area = math.sqrt(area / math.pi)
        
        # 从周长计算半径
        radius_from_perimeter = perimeter / (2 * math.pi)
        
        circle.add_tag(f"circle_{i}")
        circle.set_metadata("area", area)
        circle.set_metadata("perimeter", perimeter)
        circle.set_metadata("radius_from_area", radius_from_area)
        circle.set_metadata("radius_from_perimeter", radius_from_perimeter)
        
        if radius_from_area < 1.5:
            circle.add_tag("small")
        elif radius_from_area > 2.5:
            circle.add_tag("large")
        else:
            circle.add_tag("medium")
        
        print(f"圆形 {i}: 面积={area:.3f}, 周长={perimeter:.3f}, 半径={radius_from_area:.3f}")

analyze_face_geometry()
```

### 带孔的面

```python
from simplecadapi import (
    make_rectangle_rface,
    make_circle_rface,
    make_face_from_wire_rface,
    make_rectangle_rwire,
    make_circle_rwire
)

def create_face_with_holes():
    """创建带孔的面（概念示例）"""
    
    # 创建外边界
    outer_boundary = make_rectangle_rwire(width=10, height=8)
    
    # 创建内边界（孔）
    hole1 = make_circle_rwire(center=(3, 2, 0), radius=1.0)
    hole2 = make_circle_rwire(center=(7, 6, 0), radius=1.5)
    
    # 注意：SimpleCAD 当前版本可能不直接支持多边界面
    # 这里展示概念和标签使用
    
    # 主面
    main_face = make_rectangle_rface(width=10, height=8)
    main_face.add_tag("main_surface")
    main_face.add_tag("with_holes")
    
    # 孔面（用于布尔运算）
    hole_face1 = make_circle_rface(center=(3, 2, 0), radius=1.0)
    hole_face1.add_tag("hole")
    hole_face1.add_tag("circular")
    hole_face1.set_metadata("hole_id", 1)
    hole_face1.set_metadata("center", (3, 2, 0))
    hole_face1.set_metadata("radius", 1.0)
    
    hole_face2 = make_circle_rface(center=(7, 6, 0), radius=1.5)
    hole_face2.add_tag("hole")
    hole_face2.add_tag("circular")
    hole_face2.set_metadata("hole_id", 2)
    hole_face2.set_metadata("center", (7, 6, 0))
    hole_face2.set_metadata("radius", 1.5)
    
    # 计算有效面积
    main_area = main_face.get_area()
    hole1_area = hole_face1.get_area()
    hole2_area = hole_face2.get_area()
    effective_area = main_area - hole1_area - hole2_area
    
    main_face.set_metadata("total_area", main_area)
    main_face.set_metadata("hole_area", hole1_area + hole2_area)
    main_face.set_metadata("effective_area", effective_area)
    
    print(f"主面面积: {main_area:.3f}")
    print(f"孔面积总和: {hole1_area + hole2_area:.3f}")
    print(f"有效面积: {effective_area:.3f}")
    
    return main_face, [hole_face1, hole_face2]

main_face, holes = create_face_with_holes()
```

### 面的变换和操作

```python
from simplecadapi import (
    make_rectangle_rface,
    translate_shape,
    rotate_shape
)

def transform_faces():
    """变换面的操作"""
    
    # 创建基础面
    base_face = make_rectangle_rface(width=4, height=3)
    base_face.add_tag("base")
    base_face.add_tag("original")
    
    # 应用变换
    translated_face = translate_shape(base_face, offset=(6, 0, 0))
    translated_face.add_tag("translated")
    
    rotated_face = rotate_shape(base_face, axis=(0, 0, 1), angle=45)
    rotated_face.add_tag("rotated")
    
    elevated_face = translate_shape(base_face, offset=(0, 0, 2))
    elevated_face.add_tag("elevated")
    
    # 收集所有面
    all_faces = [base_face, translated_face, rotated_face, elevated_face]
    
    # 分析变换结果
    for face in all_faces:
        area = face.get_area()
        normal = face.get_normal_at()
        outer_wire = face.get_outer_wire()
        edges = outer_wire.get_edges()
        
        # 计算边界框
        all_coords = []
        for edge in edges:
            start_coords = edge.get_start_vertex().get_coordinates()
            end_coords = edge.get_end_vertex().get_coordinates()
            all_coords.extend([start_coords, end_coords])
        
        if all_coords:
            min_x = min(coord[0] for coord in all_coords)
            max_x = max(coord[0] for coord in all_coords)
            min_y = min(coord[1] for coord in all_coords)
            max_y = max(coord[1] for coord in all_coords)
            min_z = min(coord[2] for coord in all_coords)
            max_z = max(coord[2] for coord in all_coords)
            
            face.set_metadata("bbox_min", (min_x, min_y, min_z))
            face.set_metadata("bbox_max", (max_x, max_y, max_z))
        
        face.set_metadata("area", area)
        face.set_metadata("normal", (normal.x, normal.y, normal.z))
        
        print(f"面标签: {face.get_tags()}")
        print(f"  面积: {area:.3f}")
        print(f"  法向量: ({normal.x:.3f}, {normal.y:.3f}, {normal.z:.3f})")
        if face.get_metadata("bbox_min"):
            print(f"  边界框: {face.get_metadata('bbox_min')} 到 {face.get_metadata('bbox_max')}")
        print()

transform_faces()
```

### 面的分类和筛选

```python
from simplecadapi import make_rectangle_rface, make_circle_rface

def classify_faces():
    """分类和筛选面"""
    
    # 创建不同类型的面
    faces = []
    
    # 小矩形
    small_rects = [
        make_rectangle_rface(width=1, height=1),
        make_rectangle_rface(width=2, height=1),
        make_rectangle_rface(width=1, height=2)
    ]
    
    # 大矩形
    large_rects = [
        make_rectangle_rface(width=5, height=4),
        make_rectangle_rface(width=6, height=3),
        make_rectangle_rface(width=4, height=6)
    ]
    
    # 圆形
    circles = [
        make_circle_rface(center=(0, 0, 0), radius=1.0),
        make_circle_rface(center=(0, 0, 0), radius=2.0),
        make_circle_rface(center=(0, 0, 0), radius=3.0)
    ]
    
    # 标记面
    for i, face in enumerate(small_rects):
        face.add_tag("rectangle")
        face.add_tag("small")
        face.set_metadata("size_category", "small")
        face.set_metadata("shape_type", "rectangle")
        faces.append(face)
    
    for i, face in enumerate(large_rects):
        face.add_tag("rectangle")
        face.add_tag("large")
        face.set_metadata("size_category", "large")
        face.set_metadata("shape_type", "rectangle")
        faces.append(face)
    
    for i, face in enumerate(circles):
        face.add_tag("circle")
        area = face.get_area()
        if area < 10:
            face.add_tag("small")
            face.set_metadata("size_category", "small")
        elif area > 20:
            face.add_tag("large")
            face.set_metadata("size_category", "large")
        else:
            face.add_tag("medium")
            face.set_metadata("size_category", "medium")
        face.set_metadata("shape_type", "circle")
        faces.append(face)
    
    # 分类统计
    rectangles = [f for f in faces if f.has_tag("rectangle")]
    circles = [f for f in faces if f.has_tag("circle")]
    small_faces = [f for f in faces if f.has_tag("small")]
    large_faces = [f for f in faces if f.has_tag("large")]
    
    print(f"总面数: {len(faces)}")
    print(f"矩形面: {len(rectangles)}")
    print(f"圆形面: {len(circles)}")
    print(f"小面: {len(small_faces)}")
    print(f"大面: {len(large_faces)}")
    
    # 计算统计信息
    total_area = sum(f.get_area() for f in faces)
    avg_area = total_area / len(faces)
    
    print(f"总面积: {total_area:.3f}")
    print(f"平均面积: {avg_area:.3f}")
    
    return faces

classified_faces = classify_faces()
```

## 字符串表示

```python
from simplecadapi import make_rectangle_rface

face = make_rectangle_rface(width=5, height=3)
face.add_tag("example_face")
face.set_metadata("material", "steel")

print(face)
```

输出：
```
Face:
  area: 15.000
  normal: [0.000, 0.000, 1.000]
  outer_wire:
    Wire:
      edge_count: 4
      closed: True
      edges:
        edge_0:
          length: 5.000
          vertices:
            start: (0.0, 0.0, 0.0)
            end: (5.0, 0.0, 0.0)
        edge_1:
          length: 3.000
          vertices:
            start: (5.0, 0.0, 0.0)
            end: (5.0, 3.0, 0.0)
        edge_2:
          length: 5.000
          vertices:
            start: (5.0, 3.0, 0.0)
            end: (0.0, 3.0, 0.0)
        edge_3:
          length: 3.000
          vertices:
            start: (0.0, 3.0, 0.0)
            end: (0.0, 0.0, 0.0)
  tags: [example_face]
  metadata:
    material: steel
```

## 与其他几何体的关系

- **线 (Wire)**: 面的边界
- **边 (Edge)**: 通过线间接关联
- **实体 (Solid)**: 面构成实体的表面
- **壳 (Shell)**: 多个面组成的表面集合

## 注意事项

- 面必须是封闭的，由闭合的线围成
- 面的法向量方向遵循右手定则
- 面积计算包括所有边界围成的区域
- 带孔的面需要特殊处理（外边界 + 内边界）
- 面的方向性影响后续的实体操作
- 复杂面可能存在自相交或退化情况
- 参数 u, v 的取值范围通常是 [0, 1]
