# Solid 实体

## 概述

`Solid` 是 SimpleCAD API 中的实体类，表示三维封闭的几何体。实体具有体积，是 CAD 建模中最重要的几何类型之一。它包装了 CADQuery 的 Solid 对象，并添加了标签功能和面的自动标记能力。

## 类定义

```python
class Solid(TaggedMixin):
    """实体类，包装CADQuery的Solid，添加标签功能"""
```

## 继承关系

- 继承自 `TaggedMixin`，具有标签和元数据功能

## 用途

- 表示三维实体对象
- 进行布尔运算（并集、交集、差集）
- 应用特征操作（倒角、圆角等）
- 计算体积、表面积等物理属性
- 生成制造数据

## 构造函数

### `__init__(cq_solid)`

初始化实体对象。

**参数:**
- `cq_solid` (Union[cadquery.Solid, Any]): CADQuery 的实体对象或其他 Shape 对象

**异常:**
- `ValueError`: 当输入的实体对象无效时抛出

**示例:**
```python
from simplecadapi import (
    make_box_rsolid,
    make_cylinder_rsolid,
    make_sphere_rsolid
)

# 通过 SimpleCAD 函数创建实体
box = make_box_rsolid(width=5, height=3, depth=2)
cylinder = make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=4)
sphere = make_sphere_rsolid(center=(0, 0, 0), radius=1.5)
```

## 主要属性

- `cq_solid`: 底层的 CADQuery 实体对象
- `_tags`: 标签集合（继承自 TaggedMixin）
- `_metadata`: 元数据字典（继承自 TaggedMixin）
- `_face_tags`: 面标签字典（内部使用）

## 常用方法

### `get_volume()`

获取实体的体积。

**返回:**
- `float`: 实体的体积

**异常:**
- `ValueError`: 获取体积失败时抛出

**示例:**
```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid, make_sphere_rsolid
import math

# 立方体体积
box = make_box_rsolid(width=2, height=3, depth=4)
box_volume = box.get_volume()
print(f"立方体体积: {box_volume}")  # 24.0

# 圆柱体体积
cylinder = make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=5)
cylinder_volume = cylinder.get_volume()
expected_volume = math.pi * 2**2 * 5
print(f"圆柱体体积: {cylinder_volume:.3f}, 期望: {expected_volume:.3f}")

# 球体体积
sphere = make_sphere_rsolid(center=(0, 0, 0), radius=1.5)
sphere_volume = sphere.get_volume()
expected_volume = (4/3) * math.pi * 1.5**3
print(f"球体体积: {sphere_volume:.3f}, 期望: {expected_volume:.3f}")
```

### `get_faces()`

获取组成实体的所有面。

**返回:**
- `List[Face]`: 面对象列表

**异常:**
- `ValueError`: 获取面列表失败时抛出

**示例:**
```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=4, height=3, depth=2)
faces = box.get_faces()

print(f"立方体有 {len(faces)} 个面")
for i, face in enumerate(faces):
    area = face.get_area()
    print(f"面 {i}: 面积 {area:.3f}")
```

### `get_edges()`

获取组成实体的所有边。

**返回:**
- `List[Edge]`: 边对象列表

**异常:**
- `ValueError`: 获取边列表失败时抛出

**示例:**
```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=4, height=3, depth=2)
edges = box.get_edges()

print(f"立方体有 {len(edges)} 条边")
for i, edge in enumerate(edges):
    length = edge.get_length()
    print(f"边 {i}: 长度 {length:.3f}")
```

### `auto_tag_faces(geometry_type)`

自动为面添加标签。

**参数:**
- `geometry_type` (str): 几何体类型（"box"、"cylinder"、"sphere"、"unknown"）

**示例:**
```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid

# 立方体面标记
box = make_box_rsolid(width=4, height=3, depth=2)
box.auto_tag_faces("box")

faces = box.get_faces()
for face in faces:
    print(f"面标签: {face.get_tags()}")

# 圆柱体面标记
cylinder = make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=4)
cylinder.auto_tag_faces("cylinder")

faces = cylinder.get_faces()
for face in faces:
    print(f"面标签: {face.get_tags()}")
```

### 标签管理方法

继承自 `TaggedMixin` 的方法：

#### `add_tag(tag)`、`has_tag(tag)`、`get_tags()`、`remove_tag(tag)`
#### `set_metadata(key, value)`、`get_metadata(key, default=None)`

使用方法与 Vertex 类似，详见 [Vertex 文档](vertex.md)。

## 使用示例

### 创建和分析基础实体

```python
from simplecadapi import (
    make_box_rsolid,
    make_cylinder_rsolid,
    make_sphere_rsolid
)

def create_basic_solids():
    """创建和分析基础实体"""
    
    # 创建不同类型的实体
    solids = [
        ("box", make_box_rsolid(width=4, height=3, depth=2)),
        ("cylinder", make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=4)),
        ("sphere", make_sphere_rsolid(center=(0, 0, 0), radius=1.5))
    ]
    
    for name, solid in solids:
        # 添加基本标签
        solid.add_tag(name)
        solid.add_tag("basic_geometry")
        
        # 自动标记面
        solid.auto_tag_faces(name)
        
        # 获取几何属性
        volume = solid.get_volume()
        faces = solid.get_faces()
        edges = solid.get_edges()
        
        # 计算表面积
        total_surface_area = sum(face.get_area() for face in faces)
        
        # 分析面的分布
        face_areas = [face.get_area() for face in faces]
        min_face_area = min(face_areas)
        max_face_area = max(face_areas)
        avg_face_area = sum(face_areas) / len(face_areas)
        
        # 存储元数据
        solid.set_metadata("volume", volume)
        solid.set_metadata("surface_area", total_surface_area)
        solid.set_metadata("face_count", len(faces))
        solid.set_metadata("edge_count", len(edges))
        solid.set_metadata("min_face_area", min_face_area)
        solid.set_metadata("max_face_area", max_face_area)
        solid.set_metadata("avg_face_area", avg_face_area)
        
        # 计算体积效率（体积/表面积比）
        volume_efficiency = volume / total_surface_area if total_surface_area > 0 else 0
        solid.set_metadata("volume_efficiency", volume_efficiency)
        
        print(f"{name.upper()} 实体分析:")
        print(f"  体积: {volume:.3f}")
        print(f"  表面积: {total_surface_area:.3f}")
        print(f"  面数: {len(faces)}")
        print(f"  边数: {len(edges)}")
        print(f"  体积效率: {volume_efficiency:.3f}")
        print(f"  面积范围: {min_face_area:.3f} - {max_face_area:.3f}")
        print()

create_basic_solids()
```

### 布尔运算示例

```python
from simplecadapi import (
    make_box_rsolid,
    make_cylinder_rsolid,
    union_rsolid,
    cut_rsolid,
    intersect_rsolid
)

def boolean_operations_example():
    """布尔运算示例"""
    
    # 创建基础几何体
    box = make_box_rsolid(width=6, height=4, depth=3)
    box.add_tag("base_box")
    
    cylinder = make_cylinder_rsolid(center=(3, 2, 0), radius=1, height=5)
    cylinder.add_tag("cutting_cylinder")
    
    # 并集运算
    union_result = union_rsolid(box, cylinder)
    union_result.add_tag("union_result")
    union_result.add_tag("combined_geometry")
    
    # 差集运算（从盒子中减去圆柱）
    cut_result = cut_rsolid(box, cylinder)
    cut_result.add_tag("cut_result")
    cut_result.add_tag("with_hole")
    
    # 交集运算
    intersect_result = intersect_rsolid(box, cylinder)
    intersect_result.add_tag("intersect_result")
    intersect_result.add_tag("common_volume")
    
    # 分析结果
    operations = [
        ("原始盒子", box),
        ("原始圆柱", cylinder),
        ("并集", union_result),
        ("差集", cut_result),
        ("交集", intersect_result)
    ]
    
    for name, solid in operations:
        volume = solid.get_volume()
        faces = solid.get_faces()
        surface_area = sum(face.get_area() for face in faces)
        
        solid.set_metadata("operation_type", name)
        solid.set_metadata("volume", volume)
        solid.set_metadata("surface_area", surface_area)
        
        print(f"{name}:")
        print(f"  体积: {volume:.3f}")
        print(f"  表面积: {surface_area:.3f}")
        print(f"  面数: {len(faces)}")
        print(f"  标签: {solid.get_tags()}")
        print()

boolean_operations_example()
```

### 特征操作示例

```python
from simplecadapi import (
    make_box_rsolid,
    fillet_rsolid,
    chamfer_rsolid,
    select_edges_by_tag
)

def feature_operations_example():
    """特征操作示例"""
    
    # 创建基础盒子
    base_box = make_box_rsolid(width=8, height=6, depth=4)
    base_box.add_tag("base_geometry")
    base_box.auto_tag_faces("box")
    
    # 分析原始几何体
    original_volume = base_box.get_volume()
    original_faces = base_box.get_faces()
    original_edges = base_box.get_edges()
    
    print(f"原始几何体:")
    print(f"  体积: {original_volume:.3f}")
    print(f"  面数: {len(original_faces)}")
    print(f"  边数: {len(original_edges)}")
    print()
    
    # 圆角操作
    try:
        filleted_box = fillet_rsolid(base_box, radius=0.5)
        filleted_box.add_tag("filleted")
        filleted_box.add_tag("rounded_edges")
        
        filleted_volume = filleted_box.get_volume()
        filleted_faces = filleted_box.get_faces()
        filleted_edges = filleted_box.get_edges()
        
        filleted_box.set_metadata("original_volume", original_volume)
        filleted_box.set_metadata("volume_change", filleted_volume - original_volume)
        filleted_box.set_metadata("volume_ratio", filleted_volume / original_volume)
        
        print(f"圆角后几何体:")
        print(f"  体积: {filleted_volume:.3f}")
        print(f"  体积变化: {filleted_volume - original_volume:.3f}")
        print(f"  面数: {len(filleted_faces)}")
        print(f"  边数: {len(filleted_edges)}")
        print()
        
    except Exception as e:
        print(f"圆角操作失败: {e}")
        filleted_box = None
    
    # 倒角操作
    try:
        chamfered_box = chamfer_rsolid(base_box, distance=0.3)
        chamfered_box.add_tag("chamfered")
        chamfered_box.add_tag("beveled_edges")
        
        chamfered_volume = chamfered_box.get_volume()
        chamfered_faces = chamfered_box.get_faces()
        chamfered_edges = chamfered_box.get_edges()
        
        chamfered_box.set_metadata("original_volume", original_volume)
        chamfered_box.set_metadata("volume_change", chamfered_volume - original_volume)
        chamfered_box.set_metadata("volume_ratio", chamfered_volume / original_volume)
        
        print(f"倒角后几何体:")
        print(f"  体积: {chamfered_volume:.3f}")
        print(f"  体积变化: {chamfered_volume - original_volume:.3f}")
        print(f"  面数: {len(chamfered_faces)}")
        print(f"  边数: {len(chamfered_edges)}")
        print()
        
    except Exception as e:
        print(f"倒角操作失败: {e}")
        chamfered_box = None
    
    # 比较结果
    results = [("原始", base_box)]
    if filleted_box:
        results.append(("圆角", filleted_box))
    if chamfered_box:
        results.append(("倒角", chamfered_box))
    
    print("特征操作比较:")
    for name, solid in results:
        volume = solid.get_volume()
        faces = solid.get_faces()
        tags = solid.get_tags()
        print(f"  {name}: 体积={volume:.3f}, 面数={len(faces)}, 标签={tags}")

feature_operations_example()
```

### 复杂几何体创建

```python
from simplecadapi import (
    make_box_rsolid,
    make_cylinder_rsolid,
    make_sphere_rsolid,
    union_rsolid,
    cut_rsolid,
    translate_shape,
    rotate_shape
)

def create_complex_geometry():
    """创建复杂几何体"""
    
    # 创建主体
    main_body = make_box_rsolid(width=12, height=8, depth=6)
    main_body.add_tag("main_body")
    main_body.add_tag("base_structure")
    
    # 创建圆柱形孔
    holes = []
    hole_positions = [(3, 2, 0), (9, 2, 0), (3, 6, 0), (9, 6, 0)]
    
    for i, (x, y, z) in enumerate(hole_positions):
        hole = make_cylinder_rsolid(center=(x, y, z), radius=0.8, height=8)
        hole.add_tag(f"hole_{i}")
        hole.add_tag("mounting_hole")
        holes.append(hole)
    
    # 创建球形特征
    sphere_feature = make_sphere_rsolid(center=(6, 4, 6), radius=2)
    sphere_feature.add_tag("sphere_feature")
    sphere_feature.add_tag("decorative")
    
    # 创建圆柱形支柱
    support_cylinder = make_cylinder_rsolid(center=(6, 4, 0), radius=1, height=4)
    support_cylinder.add_tag("support_cylinder")
    support_cylinder.add_tag("structural")
    
    # 组合几何体
    complex_solid = union_rsolid(main_body, sphere_feature)
    complex_solid = union_rsolid(complex_solid, support_cylinder)
    
    # 减去孔
    for hole in holes:
        complex_solid = cut_rsolid(complex_solid, hole)
    
    # 标记复杂几何体
    complex_solid.add_tag("complex_geometry")
    complex_solid.add_tag("multi_feature")
    complex_solid.add_tag("machined_part")
    
    # 分析复杂几何体
    volume = complex_solid.get_volume()
    faces = complex_solid.get_faces()
    edges = complex_solid.get_edges()
    
    # 计算几何复杂度
    face_count = len(faces)
    edge_count = len(edges)
    complexity_ratio = edge_count / face_count if face_count > 0 else 0
    
    # 分析面的分布
    face_areas = [face.get_area() for face in faces]
    total_surface_area = sum(face_areas)
    
    # 分类面
    small_faces = [f for f in faces if f.get_area() < 1.0]
    large_faces = [f for f in faces if f.get_area() > 10.0]
    medium_faces = [f for f in faces if 1.0 <= f.get_area() <= 10.0]
    
    # 存储分析结果
    complex_solid.set_metadata("volume", volume)
    complex_solid.set_metadata("surface_area", total_surface_area)
    complex_solid.set_metadata("face_count", face_count)
    complex_solid.set_metadata("edge_count", edge_count)
    complex_solid.set_metadata("complexity_ratio", complexity_ratio)
    complex_solid.set_metadata("small_face_count", len(small_faces))
    complex_solid.set_metadata("medium_face_count", len(medium_faces))
    complex_solid.set_metadata("large_face_count", len(large_faces))
    
    # 根据复杂度添加标签
    if complexity_ratio < 5:
        complex_solid.add_tag("simple_topology")
    elif complexity_ratio < 10:
        complex_solid.add_tag("moderate_topology")
    else:
        complex_solid.add_tag("complex_topology")
    
    print(f"复杂几何体分析:")
    print(f"  体积: {volume:.3f}")
    print(f"  表面积: {total_surface_area:.3f}")
    print(f"  面数: {face_count}")
    print(f"  边数: {edge_count}")
    print(f"  复杂度比: {complexity_ratio:.2f}")
    print(f"  面分布 - 小:{len(small_faces)}, 中:{len(medium_faces)}, 大:{len(large_faces)}")
    print(f"  标签: {complex_solid.get_tags()}")
    
    return complex_solid

complex_geometry = create_complex_geometry()
```

### 实体质量分析

```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid, make_sphere_rsolid

def analyze_solid_quality():
    """分析实体质量"""
    
    # 创建测试实体
    test_solids = [
        ("small_box", make_box_rsolid(width=1, height=1, depth=1)),
        ("large_box", make_box_rsolid(width=10, height=10, depth=10)),
        ("thin_box", make_box_rsolid(width=10, height=10, depth=0.1)),
        ("cylinder", make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=5)),
        ("sphere", make_sphere_rsolid(center=(0, 0, 0), radius=2))
    ]
    
    for name, solid in test_solids:
        solid.add_tag(name)
        solid.add_tag("test_geometry")
        
        # 基本几何属性
        volume = solid.get_volume()
        faces = solid.get_faces()
        edges = solid.get_edges()
        
        # 计算质量指标
        surface_area = sum(face.get_area() for face in faces)
        volume_to_surface_ratio = volume / surface_area if surface_area > 0 else 0
        
        # 分析拓扑复杂度
        face_count = len(faces)
        edge_count = len(edges)
        euler_characteristic = None  # 简化版本不计算欧拉特征数
        
        # 面积分布分析
        face_areas = [face.get_area() for face in faces]
        if face_areas:
            min_area = min(face_areas)
            max_area = max(face_areas)
            area_ratio = max_area / min_area if min_area > 0 else float('inf')
        else:
            min_area = max_area = area_ratio = 0
        
        # 质量评估
        quality_score = 0
        quality_issues = []
        
        # 体积检查
        if volume > 1e-6:
            quality_score += 20
        else:
            quality_issues.append("极小体积")
        
        # 面数检查
        if 4 <= face_count <= 100:
            quality_score += 20
        elif face_count > 100:
            quality_issues.append("面数过多")
        else:
            quality_issues.append("面数异常")
        
        # 面积比检查
        if area_ratio < 1000:
            quality_score += 20
        else:
            quality_issues.append("面积差异过大")
        
        # 体积效率检查
        if volume_to_surface_ratio > 0.1:
            quality_score += 20
        else:
            quality_issues.append("体积效率低")
        
        # 边数合理性检查
        if edge_count < face_count * 10:
            quality_score += 20
        else:
            quality_issues.append("边数过多")
        
        # 存储质量数据
        solid.set_metadata("volume", volume)
        solid.set_metadata("surface_area", surface_area)
        solid.set_metadata("face_count", face_count)
        solid.set_metadata("edge_count", edge_count)
        solid.set_metadata("volume_to_surface_ratio", volume_to_surface_ratio)
        solid.set_metadata("area_ratio", area_ratio)
        solid.set_metadata("quality_score", quality_score)
        solid.set_metadata("quality_issues", quality_issues)
        
        # 质量标签
        if quality_score >= 80:
            solid.add_tag("high_quality")
        elif quality_score >= 60:
            solid.add_tag("good_quality")
        elif quality_score >= 40:
            solid.add_tag("acceptable_quality")
        else:
            solid.add_tag("poor_quality")
        
        print(f"{name.upper()} 质量分析:")
        print(f"  体积: {volume:.6f}")
        print(f"  表面积: {surface_area:.3f}")
        print(f"  面数: {face_count}")
        print(f"  边数: {edge_count}")
        print(f"  体积效率: {volume_to_surface_ratio:.3f}")
        print(f"  面积比: {area_ratio:.2f}")
        print(f"  质量分数: {quality_score}/100")
        if quality_issues:
            print(f"  质量问题: {', '.join(quality_issues)}")
        print(f"  质量等级: {[tag for tag in solid.get_tags() if 'quality' in tag]}")
        print()

analyze_solid_quality()
```

## 字符串表示

```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=5, height=3, depth=2)
box.add_tag("example_box")
box.auto_tag_faces("box")
box.set_metadata("material", "aluminum")

print(box)
```

输出：
```
Solid:
  volume: 30.000
  face_count: 6
  edge_count: 12
  faces:
    face_0:
      area: 15.000
      normal: [0.000, 0.000, 1.000]
      tags: [top]
    face_1:
      area: 15.000
      normal: [0.000, 0.000, -1.000]
      tags: [bottom]
    face_2:
      area: 10.000
      normal: [0.000, 1.000, 0.000]
      tags: [front]
    face_3:
      area: 10.000
      normal: [0.000, -1.000, 0.000]
      tags: [back]
    face_4:
      area: 6.000
      normal: [1.000, 0.000, 0.000]
      tags: [right]
    face_5:
      area: 6.000
      normal: [-1.000, 0.000, 0.000]
      tags: [left]
  tags: [example_box]
  metadata:
    material: aluminum
```

## 与其他几何体的关系

- **面 (Face)**: 实体的边界表面
- **边 (Edge)**: 面的边界
- **壳 (Shell)**: 实体可以分解为壳
- **复合体 (Compound)**: 多个实体可以组成复合体

## 应用场景

- **机械设计**: 零件建模
- **建筑设计**: 建筑构件
- **产品设计**: 工业产品
- **3D 打印**: 制造原型
- **仿真分析**: 有限元分析

## 注意事项

- 实体必须是封闭的、有效的几何体
- 布尔运算可能改变实体的拓扑结构
- 复杂实体可能包含大量面和边
- 特征操作可能失败，需要适当的错误处理
- 自动面标记功能依赖于几何体的规则性
- 实体的质量直接影响后续操作的成功率和性能
