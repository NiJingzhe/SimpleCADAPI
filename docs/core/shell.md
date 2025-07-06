# Shell 壳

## 概述

`Shell` 是 SimpleCAD API 中的壳类，表示由多个面组成的开放或闭合的表面集合。壳是介于面和实体之间的几何体，可以用于创建复杂的表面结构。它包装了 CADQuery 的 Shell 对象，并添加了标签功能。

## 类定义

```python
class Shell(TaggedMixin):
    """壳类，包装CADQuery的Shell，添加标签功能"""
```

## 继承关系

- 继承自 `TaggedMixin`，具有标签和元数据功能

## 用途

- 表示复杂的表面结构
- 作为实体的中间状态
- 创建开放的表面几何体
- 表示薄壁结构

## 构造函数

### `__init__(cq_shell)`

初始化壳对象。

**参数:**
- `cq_shell` (Union[cadquery.Shell, Any]): CADQuery 的壳对象或其他 Shape 对象

**异常:**
- `ValueError`: 当输入的壳对象无效时抛出

**示例:**
```python
from simplecadapi import make_box_rsolid, shell_rsolid

# 创建一个实体，然后制作壳
box = make_box_rsolid(width=5, height=3, depth=2)
# 选择要移除的面创建壳
shell = shell_rsolid(box, thickness=0.2)  # 创建薄壁壳
```

## 主要属性

- `cq_shell`: 底层的 CADQuery 壳对象
- `_tags`: 标签集合（继承自 TaggedMixin）
- `_metadata`: 元数据字典（继承自 TaggedMixin）

## 常用方法

### `get_faces()`

获取组成壳的所有面。

**返回:**
- `List[Face]`: 面对象列表

**异常:**
- `ValueError`: 获取面列表失败时抛出

**示例:**
```python
from simplecadapi import make_box_rsolid, shell_rsolid

# 创建壳
box = make_box_rsolid(width=4, height=3, depth=2)
shell = shell_rsolid(box, thickness=0.1)

# 获取面
faces = shell.get_faces()
print(f"壳由 {len(faces)} 个面组成")

for i, face in enumerate(faces):
    area = face.get_area()
    print(f"面 {i}: 面积 {area:.3f}")
```

### 标签管理方法

继承自 `TaggedMixin` 的方法：

#### `add_tag(tag)`、`has_tag(tag)`、`get_tags()`、`remove_tag(tag)`
#### `set_metadata(key, value)`、`get_metadata(key, default=None)`

使用方法与 Vertex 类似，详见 [Vertex 文档](vertex.md)。

## 使用示例

### 创建和分析壳

```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid, shell_rsolid

def create_and_analyze_shells():
    """创建和分析不同类型的壳"""
    
    # 创建盒子壳
    box = make_box_rsolid(width=6, height=4, depth=3)
    box_shell = shell_rsolid(box, thickness=0.2)
    box_shell.add_tag("box_shell")
    box_shell.add_tag("rectangular")
    
    # 创建圆柱壳
    cylinder = make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=5)
    cylinder_shell = shell_rsolid(cylinder, thickness=0.15)
    cylinder_shell.add_tag("cylinder_shell")
    cylinder_shell.add_tag("cylindrical")
    
    # 分析壳
    shells = [box_shell, cylinder_shell]
    
    for shell in shells:
        faces = shell.get_faces()
        total_area = sum(face.get_area() for face in faces)
        
        # 分析面的类型
        face_areas = [face.get_area() for face in faces]
        min_area = min(face_areas)
        max_area = max(face_areas)
        avg_area = sum(face_areas) / len(face_areas)
        
        shell.set_metadata("face_count", len(faces))
        shell.set_metadata("total_surface_area", total_area)
        shell.set_metadata("min_face_area", min_area)
        shell.set_metadata("max_face_area", max_area)
        shell.set_metadata("avg_face_area", avg_area)
        
        # 标记面的大小
        for i, face in enumerate(faces):
            area = face.get_area()
            face.add_tag(f"shell_face_{i}")
            
            if area < avg_area * 0.5:
                face.add_tag("small_face")
            elif area > avg_area * 1.5:
                face.add_tag("large_face")
            else:
                face.add_tag("medium_face")
        
        print(f"壳类型: {shell.get_tags()}")
        print(f"  面数: {len(faces)}")
        print(f"  总表面积: {total_area:.3f}")
        print(f"  平均面积: {avg_area:.3f}")
        print(f"  面积范围: {min_area:.3f} - {max_area:.3f}")
        print()

create_and_analyze_shells()
```

### 复杂壳的创建

```python
from simplecadapi import (
    make_box_rsolid, 
    make_cylinder_rsolid, 
    union_rsolid, 
    shell_rsolid
)

def create_complex_shell():
    """创建复杂的壳结构"""
    
    # 创建复合几何体
    main_body = make_box_rsolid(width=8, height=6, depth=4)
    main_body.add_tag("main_body")
    
    # 添加圆柱形突出部分
    cylinder1 = make_cylinder_rsolid(center=(2, 1, 4), radius=1, height=2)
    cylinder1.add_tag("protrusion_1")
    
    cylinder2 = make_cylinder_rsolid(center=(6, 5, 4), radius=0.8, height=1.5)
    cylinder2.add_tag("protrusion_2")
    
    # 合并几何体
    combined = union_rsolid(main_body, cylinder1)
    combined = union_rsolid(combined, cylinder2)
    combined.add_tag("combined_solid")
    
    # 创建壳
    complex_shell = shell_rsolid(combined, thickness=0.3)
    complex_shell.add_tag("complex_shell")
    complex_shell.add_tag("multi_feature")
    
    # 分析复杂壳
    faces = complex_shell.get_faces()
    
    # 按面积分类
    large_faces = []
    medium_faces = []
    small_faces = []
    
    total_area = sum(face.get_area() for face in faces)
    avg_area = total_area / len(faces)
    
    for i, face in enumerate(faces):
        area = face.get_area()
        face.add_tag(f"complex_face_{i}")
        face.set_metadata("area", area)
        face.set_metadata("area_ratio", area / avg_area)
        
        if area > avg_area * 2:
            large_faces.append(face)
            face.add_tag("large")
        elif area > avg_area * 0.5:
            medium_faces.append(face)
            face.add_tag("medium")
        else:
            small_faces.append(face)
            face.add_tag("small")
    
    complex_shell.set_metadata("large_face_count", len(large_faces))
    complex_shell.set_metadata("medium_face_count", len(medium_faces))
    complex_shell.set_metadata("small_face_count", len(small_faces))
    complex_shell.set_metadata("total_surface_area", total_area)
    
    print(f"复杂壳分析:")
    print(f"  总面数: {len(faces)}")
    print(f"  大面数: {len(large_faces)}")
    print(f"  中面数: {len(medium_faces)}")
    print(f"  小面数: {len(small_faces)}")
    print(f"  总表面积: {total_area:.3f}")
    
    return complex_shell

complex_shell = create_complex_shell()
```

### 壳的质量检查

```python
from simplecadapi import make_box_rsolid, shell_rsolid

def check_shell_quality():
    """检查壳的质量"""
    
    # 创建测试壳
    test_solids = [
        make_box_rsolid(width=5, height=5, depth=5),  # 立方体
        make_box_rsolid(width=10, height=2, depth=1), # 薄板
        make_box_rsolid(width=1, height=1, depth=10)  # 长条
    ]
    
    test_names = ["cube", "plate", "rod"]
    
    for i, solid in enumerate(test_solids):
        name = test_names[i]
        solid.add_tag(name)
        
        # 创建不同厚度的壳
        thicknesses = [0.1, 0.2, 0.5]
        
        for thickness in thicknesses:
            try:
                shell = shell_rsolid(solid, thickness=thickness)
                shell.add_tag(f"{name}_shell")
                shell.add_tag(f"thickness_{thickness}")
                
                faces = shell.get_faces()
                
                # 检查面的连续性
                edge_count = 0
                total_area = 0
                
                for face in faces:
                    area = face.get_area()
                    total_area += area
                    
                    outer_wire = face.get_outer_wire()
                    edges = outer_wire.get_edges()
                    edge_count += len(edges)
                    
                    # 检查面的有效性
                    if area < 1e-6:
                        face.add_tag("degenerate")
                    elif area > 1000:
                        face.add_tag("oversized")
                    else:
                        face.add_tag("normal")
                
                # 计算质量指标
                face_count = len(faces)
                avg_face_area = total_area / face_count if face_count > 0 else 0
                edge_to_face_ratio = edge_count / face_count if face_count > 0 else 0
                
                shell.set_metadata("thickness", thickness)
                shell.set_metadata("face_count", face_count)
                shell.set_metadata("edge_count", edge_count)
                shell.set_metadata("total_area", total_area)
                shell.set_metadata("avg_face_area", avg_face_area)
                shell.set_metadata("edge_to_face_ratio", edge_to_face_ratio)
                
                # 质量评估
                if face_count < 20 and edge_to_face_ratio < 10:
                    shell.add_tag("good_quality")
                elif face_count < 50 and edge_to_face_ratio < 20:
                    shell.add_tag("acceptable_quality")
                else:
                    shell.add_tag("complex_geometry")
                
                print(f"{name} 壳 (厚度 {thickness}):")
                print(f"  面数: {face_count}")
                print(f"  边数: {edge_count}")
                print(f"  总面积: {total_area:.3f}")
                print(f"  边面比: {edge_to_face_ratio:.2f}")
                print(f"  质量: {shell.get_tags()}")
                print()
                
            except Exception as e:
                print(f"创建 {name} 壳 (厚度 {thickness}) 失败: {e}")
                print()

check_shell_quality()
```

### 壳的修复和优化

```python
from simplecadapi import make_box_rsolid, shell_rsolid

def optimize_shell():
    """优化壳的结构"""
    
    # 创建基础壳
    base_solid = make_box_rsolid(width=6, height=4, depth=3)
    shell = shell_rsolid(base_solid, thickness=0.2)
    shell.add_tag("original_shell")
    
    faces = shell.get_faces()
    
    # 分析和标记面
    optimized_faces = []
    removed_faces = []
    
    total_area = sum(face.get_area() for face in faces)
    avg_area = total_area / len(faces)
    
    for i, face in enumerate(faces):
        area = face.get_area()
        face.add_tag(f"face_{i}")
        face.set_metadata("original_area", area)
        
        # 检查面的质量
        if area < avg_area * 0.01:  # 极小面
            face.add_tag("tiny_face")
            face.add_tag("candidate_for_removal")
            removed_faces.append(face)
        elif area > avg_area * 10:  # 极大面
            face.add_tag("oversized_face")
            face.add_tag("needs_subdivision")
            optimized_faces.append(face)
        else:
            face.add_tag("normal_face")
            optimized_faces.append(face)
    
    # 创建优化信息
    shell.set_metadata("original_face_count", len(faces))
    shell.set_metadata("optimized_face_count", len(optimized_faces))
    shell.set_metadata("removed_face_count", len(removed_faces))
    shell.set_metadata("total_area", total_area)
    
    # 标记优化结果
    if len(removed_faces) > 0:
        shell.add_tag("has_removable_faces")
    
    if len(optimized_faces) == len(faces):
        shell.add_tag("well_formed")
    else:
        shell.add_tag("needs_optimization")
    
    print(f"壳优化分析:")
    print(f"  原始面数: {len(faces)}")
    print(f"  优化后面数: {len(optimized_faces)}")
    print(f"  移除面数: {len(removed_faces)}")
    print(f"  总面积: {total_area:.3f}")
    print(f"  平均面积: {avg_area:.3f}")
    print(f"  优化标签: {shell.get_tags()}")
    
    return shell, optimized_faces, removed_faces

shell, optimized_faces, removed_faces = optimize_shell()
```

### 壳的比较和分析

```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid, shell_rsolid

def compare_shells():
    """比较不同类型的壳"""
    
    # 创建不同的基础几何体
    geometries = [
        ("box", make_box_rsolid(width=4, height=4, depth=4)),
        ("cylinder", make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=4)),
    ]
    
    shells = []
    
    for name, geometry in geometries:
        # 创建不同厚度的壳
        for thickness in [0.1, 0.2, 0.3]:
            shell = shell_rsolid(geometry, thickness=thickness)
            shell.add_tag(f"{name}_shell")
            shell.add_tag(f"thickness_{thickness}")
            
            faces = shell.get_faces()
            
            # 计算几何属性
            total_area = sum(face.get_area() for face in faces)
            face_count = len(faces)
            
            # 计算复杂度指标
            edge_count = sum(len(face.get_outer_wire().get_edges()) for face in faces)
            complexity = edge_count / face_count if face_count > 0 else 0
            
            shell.set_metadata("base_geometry", name)
            shell.set_metadata("thickness", thickness)
            shell.set_metadata("face_count", face_count)
            shell.set_metadata("edge_count", edge_count)
            shell.set_metadata("total_area", total_area)
            shell.set_metadata("complexity", complexity)
            
            # 分类复杂度
            if complexity < 5:
                shell.add_tag("simple")
            elif complexity < 8:
                shell.add_tag("moderate")
            else:
                shell.add_tag("complex")
            
            shells.append(shell)
    
    # 比较分析
    print("壳比较分析:")
    print("=" * 50)
    
    for shell in shells:
        base_geo = shell.get_metadata("base_geometry")
        thickness = shell.get_metadata("thickness")
        face_count = shell.get_metadata("face_count")
        total_area = shell.get_metadata("total_area")
        complexity = shell.get_metadata("complexity")
        
        print(f"{base_geo} 壳 (厚度 {thickness}):")
        print(f"  面数: {face_count}")
        print(f"  总面积: {total_area:.3f}")
        print(f"  复杂度: {complexity:.2f}")
        print(f"  分类: {[tag for tag in shell.get_tags() if tag in ['simple', 'moderate', 'complex']]}")
        print()
    
    return shells

shell_comparison = compare_shells()
```

## 字符串表示

```python
from simplecadapi import make_box_rsolid, shell_rsolid

box = make_box_rsolid(width=5, height=3, depth=2)
shell = shell_rsolid(box, thickness=0.2)
shell.add_tag("example_shell")
shell.set_metadata("thickness", 0.2)

print(shell)
```

输出：
```
Shell:
  face_count: 10
  faces:
    face_0:
      area: 6.000
      normal: [0.000, 0.000, 1.000]
      outer_wire:
        Wire:
          edge_count: 4
          closed: True
    face_1:
      area: 6.000
      normal: [0.000, 0.000, -1.000]
      outer_wire:
        Wire:
          edge_count: 4
          closed: True
    ...
  tags: [example_shell]
  metadata:
    thickness: 0.2
```

## 与其他几何体的关系

- **面 (Face)**: 壳的组成元素
- **实体 (Solid)**: 壳可以封闭形成实体
- **复合体 (Compound)**: 多个壳可以组成复合体

## 应用场景

- **薄壁结构**: 容器、外壳等
- **建筑表面**: 建筑物的外立面
- **工业设计**: 产品外观设计
- **有限元分析**: 薄壁结构的网格生成

## 注意事项

- 壳可能是开放的或闭合的
- 闭合的壳可以形成实体
- 壳的厚度影响最终的几何形状
- 复杂壳可能包含大量小面，影响性能
- 壳的质量直接影响后续操作的成功率
- 某些操作可能导致壳的拓扑结构发生变化
