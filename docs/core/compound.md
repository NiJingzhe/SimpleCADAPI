# Compound 复合体

## 概述

`Compound` 是 SimpleCAD API 中的复合体类，表示由多个几何体组成的集合。复合体可以包含多个实体、面、边等不同类型的几何对象，是处理复杂装配体和多体几何的重要工具。它包装了 CADQuery 的 Compound 对象，并添加了标签功能。

## 类定义

```python
class Compound(TaggedMixin):
    """复合体类，包装CADQuery的Compound，添加标签功能"""
```

## 继承关系

- 继承自 `TaggedMixin`，具有标签和元数据功能

## 用途

- 管理多个几何对象的集合
- 创建复杂的装配体结构
- 批量处理多个几何体
- 组织和分类几何对象
- 实现分层的几何结构

## 构造函数

### `__init__(cq_compound)`

初始化复合体对象。

**参数:**
- `cq_compound` (cadquery.Compound): CADQuery 的复合体对象

**异常:**
- `ValueError`: 当输入的复合体对象无效时抛出

**示例:**
```python
from simplecadapi import (
    make_box_rsolid,
    make_cylinder_rsolid,
    make_sphere_rsolid,
    union_rsolid
)

# 创建多个实体
box = make_box_rsolid(width=2, height=2, depth=2)
cylinder = make_cylinder_rsolid(center=(3, 0, 0), radius=1, height=2)
sphere = make_sphere_rsolid(center=(0, 3, 0), radius=1)

# 通过布尔运算可能产生复合体
# 注意：实际的复合体创建方式可能因 API 实现而异
```

## 主要属性

- `cq_compound`: 底层的 CADQuery 复合体对象
- `_tags`: 标签集合（继承自 TaggedMixin）
- `_metadata`: 元数据字典（继承自 TaggedMixin）

## 常用方法

### `get_solids()`

获取组成复合体的所有实体。

**返回:**
- `List[Solid]`: 实体对象列表

**异常:**
- `ValueError`: 获取实体列表失败时抛出

**示例:**
```python
# 假设有一个复合体对象
# compound = ... 某个复合体

solids = compound.get_solids()
print(f"复合体包含 {len(solids)} 个实体")

for i, solid in enumerate(solids):
    volume = solid.get_volume()
    print(f"实体 {i}: 体积 {volume:.3f}")
```

### 标签管理方法

继承自 `TaggedMixin` 的方法：

#### `add_tag(tag)`、`has_tag(tag)`、`get_tags()`、`remove_tag(tag)`
#### `set_metadata(key, value)`、`get_metadata(key, default=None)`

使用方法与 Vertex 类似，详见 [Vertex 文档](vertex.md)。

## 使用示例

### 创建和管理复合体

```python
from simplecadapi import (
    make_box_rsolid,
    make_cylinder_rsolid,
    make_sphere_rsolid,
    translate_shape,
    rotate_shape
)

def create_compound_assembly():
    """创建复合体装配"""
    
    # 创建基础零件
    parts = []
    
    # 主体零件
    main_body = make_box_rsolid(width=8, height=6, depth=4)
    main_body.add_tag("main_body")
    main_body.add_tag("structural")
    main_body.set_metadata("part_id", "MB001")
    main_body.set_metadata("material", "steel")
    parts.append(main_body)
    
    # 圆柱形零件
    for i in range(3):
        cylinder = make_cylinder_rsolid(center=(0, 0, 0), radius=0.5, height=2)
        cylinder = translate_shape(cylinder, offset=(2 + i*2, 1, 4))
        cylinder.add_tag(f"cylinder_{i}")
        cylinder.add_tag("fastener")
        cylinder.set_metadata("part_id", f"CY{i:03d}")
        cylinder.set_metadata("material", "brass")
        parts.append(cylinder)
    
    # 球形零件
    for i in range(2):
        sphere = make_sphere_rsolid(center=(0, 0, 0), radius=0.8)
        sphere = translate_shape(sphere, offset=(1 + i*6, 5, 2))
        sphere.add_tag(f"sphere_{i}")
        sphere.add_tag("decorative")
        sphere.set_metadata("part_id", f"SP{i:03d}")
        sphere.set_metadata("material", "aluminum")
        parts.append(sphere)
    
    # 分析装配体
    print(f"装配体分析:")
    print(f"  零件总数: {len(parts)}")
    
    # 按类型分类
    structural_parts = [p for p in parts if p.has_tag("structural")]
    fastener_parts = [p for p in parts if p.has_tag("fastener")]
    decorative_parts = [p for p in parts if p.has_tag("decorative")]
    
    print(f"  结构件: {len(structural_parts)}")
    print(f"  紧固件: {len(fastener_parts)}")
    print(f"  装饰件: {len(decorative_parts)}")
    
    # 按材料分类
    materials = {}
    for part in parts:
        material = part.get_metadata("material", "unknown")
        if material not in materials:
            materials[material] = []
        materials[material].append(part)
    
    print(f"  材料分布:")
    for material, part_list in materials.items():
        total_volume = sum(p.get_volume() for p in part_list)
        print(f"    {material}: {len(part_list)} 件, 总体积: {total_volume:.3f}")
    
    return parts

assembly_parts = create_compound_assembly()
```

### 复合体的层次结构

```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid, translate_shape

def create_hierarchical_compound():
    """创建层次化复合体"""
    
    # 创建子装配1：螺栓组件
    bolt_assembly = []
    
    # 螺栓主体
    bolt_body = make_cylinder_rsolid(center=(0, 0, 0), radius=0.3, height=3)
    bolt_body.add_tag("bolt_body")
    bolt_body.add_tag("threaded")
    bolt_body.set_metadata("assembly", "bolt_assembly")
    bolt_body.set_metadata("function", "fastening")
    bolt_assembly.append(bolt_body)
    
    # 螺栓头
    bolt_head = make_cylinder_rsolid(center=(0, 0, 3), radius=0.5, height=0.5)
    bolt_head.add_tag("bolt_head")
    bolt_head.add_tag("hex_head")
    bolt_head.set_metadata("assembly", "bolt_assembly")
    bolt_head.set_metadata("function", "driving")
    bolt_assembly.append(bolt_head)
    
    # 创建子装配2：支架组件
    bracket_assembly = []
    
    # 支架主体
    bracket_main = make_box_rsolid(width=4, height=1, depth=2)
    bracket_main.add_tag("bracket_main")
    bracket_main.add_tag("mounting")
    bracket_main.set_metadata("assembly", "bracket_assembly")
    bracket_main.set_metadata("function", "support")
    bracket_assembly.append(bracket_main)
    
    # 支架臂
    for i in range(2):
        arm = make_box_rsolid(width=0.5, height=2, depth=2)
        arm = translate_shape(arm, offset=(0.75 + i*2.5, 1, 0))
        arm.add_tag(f"bracket_arm_{i}")
        arm.add_tag("support_arm")
        arm.set_metadata("assembly", "bracket_assembly")
        arm.set_metadata("function", "support")
        bracket_assembly.append(arm)
    
    # 创建主装配
    main_assembly = []
    
    # 添加子装配
    main_assembly.extend(bolt_assembly)
    main_assembly.extend(bracket_assembly)
    
    # 添加主体零件
    main_body = make_box_rsolid(width=8, height=6, depth=4)
    main_body.add_tag("main_body")
    main_body.add_tag("primary_structure")
    main_body.set_metadata("assembly", "main_assembly")
    main_body.set_metadata("function", "housing")
    main_assembly.append(main_body)
    
    # 分析层次结构
    print(f"层次化装配体分析:")
    
    # 按装配分组
    assemblies = {}
    for part in main_assembly:
        assembly_name = part.get_metadata("assembly", "unknown")
        if assembly_name not in assemblies:
            assemblies[assembly_name] = []
        assemblies[assembly_name].append(part)
    
    for assembly_name, parts in assemblies.items():
        print(f"  {assembly_name}:")
        print(f"    零件数: {len(parts)}")
        
        # 按功能分类
        functions = {}
        for part in parts:
            function = part.get_metadata("function", "unknown")
            if function not in functions:
                functions[function] = []
            functions[function].append(part)
        
        for function, func_parts in functions.items():
            total_volume = sum(p.get_volume() for p in func_parts)
            print(f"      {function}: {len(func_parts)} 件, 体积: {total_volume:.3f}")
    
    return main_assembly, assemblies

main_assembly, assemblies = create_hierarchical_compound()
```

### 复合体的批量操作

```python
from simplecadapi import (
    make_box_rsolid,
    make_cylinder_rsolid,
    translate_shape,
    rotate_shape
)

def batch_operations_on_compound():
    """对复合体进行批量操作"""
    
    # 创建一系列相似零件
    parts = []
    
    # 创建网格排列的零件
    for i in range(3):
        for j in range(3):
            # 基础几何体
            if (i + j) % 2 == 0:
                part = make_box_rsolid(width=1, height=1, depth=1)
                part.add_tag("box_part")
                part.add_tag("cubic")
            else:
                part = make_cylinder_rsolid(center=(0, 0, 0), radius=0.5, height=1)
                part.add_tag("cylinder_part")
                part.add_tag("circular")
            
            # 定位
            part = translate_shape(part, offset=(i*2, j*2, 0))
            
            # 添加位置信息
            part.add_tag(f"pos_{i}_{j}")
            part.add_tag("grid_item")
            part.set_metadata("grid_position", (i, j))
            part.set_metadata("grid_index", i*3 + j)
            
            parts.append(part)
    
    # 批量分析
    print(f"批量操作分析:")
    print(f"  总零件数: {len(parts)}")
    
    # 按类型统计
    box_parts = [p for p in parts if p.has_tag("box_part")]
    cylinder_parts = [p for p in parts if p.has_tag("cylinder_part")]
    
    print(f"  盒子零件: {len(box_parts)}")
    print(f"  圆柱零件: {len(cylinder_parts)}")
    
    # 批量体积计算
    total_volume = sum(p.get_volume() for p in parts)
    box_volume = sum(p.get_volume() for p in box_parts)
    cylinder_volume = sum(p.get_volume() for p in cylinder_parts)
    
    print(f"  总体积: {total_volume:.3f}")
    print(f"  盒子体积: {box_volume:.3f}")
    print(f"  圆柱体积: {cylinder_volume:.3f}")
    
    # 批量属性设置
    for part in parts:
        volume = part.get_volume()
        grid_pos = part.get_metadata("grid_position")
        
        # 根据体积分类
        if volume < 0.5:
            part.add_tag("small_part")
        elif volume < 1.5:
            part.add_tag("medium_part")
        else:
            part.add_tag("large_part")
        
        # 根据位置分类
        if grid_pos[0] == 0:
            part.add_tag("left_column")
        elif grid_pos[0] == 2:
            part.add_tag("right_column")
        else:
            part.add_tag("center_column")
        
        if grid_pos[1] == 0:
            part.add_tag("bottom_row")
        elif grid_pos[1] == 2:
            part.add_tag("top_row")
        else:
            part.add_tag("center_row")
        
        # 设置材料属性
        if part.has_tag("box_part"):
            part.set_metadata("material", "aluminum")
            part.set_metadata("density", 2.7)
        else:
            part.set_metadata("material", "steel")
            part.set_metadata("density", 7.8)
        
        # 计算质量
        density = part.get_metadata("density")
        mass = volume * density
        part.set_metadata("mass", mass)
    
    # 批量质量分析
    total_mass = sum(p.get_metadata("mass") for p in parts)
    aluminum_mass = sum(p.get_metadata("mass") for p in parts if p.get_metadata("material") == "aluminum")
    steel_mass = sum(p.get_metadata("mass") for p in parts if p.get_metadata("material") == "steel")
    
    print(f"  总质量: {total_mass:.3f}")
    print(f"  铝质量: {aluminum_mass:.3f}")
    print(f"  钢质量: {steel_mass:.3f}")
    
    # 位置统计
    position_stats = {}
    for part in parts:
        pos = part.get_metadata("grid_position")
        if pos not in position_stats:
            position_stats[pos] = {"count": 0, "volume": 0, "mass": 0}
        
        position_stats[pos]["count"] += 1
        position_stats[pos]["volume"] += part.get_volume()
        position_stats[pos]["mass"] += part.get_metadata("mass")
    
    print(f"  位置统计:")
    for pos, stats in position_stats.items():
        print(f"    位置 {pos}: {stats['count']} 件, 体积: {stats['volume']:.3f}, 质量: {stats['mass']:.3f}")
    
    return parts

batch_parts = batch_operations_on_compound()
```

### 复合体的查询和筛选

```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid, make_sphere_rsolid

def query_and_filter_compound():
    """查询和筛选复合体"""
    
    # 创建多样化的零件集合
    parts = []
    
    # 创建不同类型的零件
    geometries = [
        ("small_box", make_box_rsolid(width=1, height=1, depth=1)),
        ("large_box", make_box_rsolid(width=3, height=2, depth=2)),
        ("thin_cylinder", make_cylinder_rsolid(center=(0, 0, 0), radius=0.5, height=4)),
        ("wide_cylinder", make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=1)),
        ("small_sphere", make_sphere_rsolid(center=(0, 0, 0), radius=0.8)),
        ("large_sphere", make_sphere_rsolid(center=(0, 0, 0), radius=1.5))
    ]
    
    # 为每个零件添加详细信息
    for name, part in geometries:
        part.add_tag(name)
        
        # 几何类型标签
        if "box" in name:
            part.add_tag("rectangular")
            part.add_tag("prismatic")
        elif "cylinder" in name:
            part.add_tag("cylindrical")
            part.add_tag("rotational")
        elif "sphere" in name:
            part.add_tag("spherical")
            part.add_tag("rotational")
        
        # 尺寸标签
        volume = part.get_volume()
        if volume < 2:
            part.add_tag("small")
        elif volume < 10:
            part.add_tag("medium")
        else:
            part.add_tag("large")
        
        # 应用标签
        if "thin" in name:
            part.add_tag("structural")
            part.set_metadata("application", "support")
        elif "wide" in name:
            part.add_tag("base")
            part.set_metadata("application", "foundation")
        else:
            part.add_tag("general")
            part.set_metadata("application", "multipurpose")
        
        # 材料属性
        if part.has_tag("small"):
            part.set_metadata("material", "aluminum")
            part.set_metadata("cost_per_unit", 2.5)
        elif part.has_tag("medium"):
            part.set_metadata("material", "steel")
            part.set_metadata("cost_per_unit", 1.8)
        else:
            part.set_metadata("material", "cast_iron")
            part.set_metadata("cost_per_unit", 3.2)
        
        part.set_metadata("volume", volume)
        part.set_metadata("name", name)
        
        parts.append(part)
    
    # 查询和筛选示例
    print(f"复合体查询和筛选:")
    print(f"  总零件数: {len(parts)}")
    
    # 1. 按标签查询
    print(f"\n1. 按标签查询:")
    small_parts = [p for p in parts if p.has_tag("small")]
    cylindrical_parts = [p for p in parts if p.has_tag("cylindrical")]
    structural_parts = [p for p in parts if p.has_tag("structural")]
    
    print(f"  小型零件: {len(small_parts)}")
    print(f"  圆柱形零件: {len(cylindrical_parts)}")
    print(f"  结构零件: {len(structural_parts)}")
    
    # 2. 按体积范围查询
    print(f"\n2. 按体积范围查询:")
    volume_ranges = [
        ("超小", 0, 1),
        ("小", 1, 5),
        ("中", 5, 15),
        ("大", 15, float('inf'))
    ]
    
    for range_name, min_vol, max_vol in volume_ranges:
        range_parts = [p for p in parts if min_vol <= p.get_volume() < max_vol]
        if range_parts:
            print(f"  {range_name}体积 ({min_vol}-{max_vol}): {len(range_parts)} 件")
    
    # 3. 按材料查询
    print(f"\n3. 按材料查询:")
    materials = set(p.get_metadata("material") for p in parts)
    for material in materials:
        material_parts = [p for p in parts if p.get_metadata("material") == material]
        total_volume = sum(p.get_volume() for p in material_parts)
        total_cost = sum(p.get_metadata("cost_per_unit", 0) for p in material_parts)
        print(f"  {material}: {len(material_parts)} 件, 总体积: {total_volume:.3f}, 总成本: {total_cost:.2f}")
    
    # 4. 复合查询
    print(f"\n4. 复合查询:")
    
    # 查询小型圆柱形零件
    small_cylinders = [p for p in parts if p.has_tag("small") and p.has_tag("cylindrical")]
    print(f"  小型圆柱形零件: {len(small_cylinders)}")
    
    # 查询铝制零件
    aluminum_parts = [p for p in parts if p.get_metadata("material") == "aluminum"]
    print(f"  铝制零件: {len(aluminum_parts)}")
    
    # 查询高成本零件
    high_cost_parts = [p for p in parts if p.get_metadata("cost_per_unit", 0) > 3.0]
    print(f"  高成本零件: {len(high_cost_parts)}")
    
    # 5. 统计分析
    print(f"\n5. 统计分析:")
    
    # 按几何类型统计
    geometric_types = ["rectangular", "cylindrical", "spherical"]
    for geo_type in geometric_types:
        type_parts = [p for p in parts if p.has_tag(geo_type)]
        if type_parts:
            avg_volume = sum(p.get_volume() for p in type_parts) / len(type_parts)
            print(f"  {geo_type}: {len(type_parts)} 件, 平均体积: {avg_volume:.3f}")
    
    # 成本效率分析
    print(f"\n6. 成本效率分析:")
    for part in parts:
        volume = part.get_volume()
        cost = part.get_metadata("cost_per_unit", 0)
        if cost > 0:
            efficiency = volume / cost
            part.set_metadata("volume_cost_efficiency", efficiency)
    
    # 按效率排序
    sorted_parts = sorted(parts, key=lambda p: p.get_metadata("volume_cost_efficiency", 0), reverse=True)
    print(f"  最高效率零件: {sorted_parts[0].get_metadata('name')}, 效率: {sorted_parts[0].get_metadata('volume_cost_efficiency'):.3f}")
    print(f"  最低效率零件: {sorted_parts[-1].get_metadata('name')}, 效率: {sorted_parts[-1].get_metadata('volume_cost_efficiency'):.3f}")
    
    return parts

filtered_parts = query_and_filter_compound()
```

## 字符串表示

```python
# 假设有一个复合体对象
# compound = ... 某个复合体

compound.add_tag("assembly")
compound.set_metadata("part_count", 5)
compound.set_metadata("total_volume", 150.0)

print(compound)
```

输出：
```
Compound:
  solid_count: 5
  solids:
    solid_0:
      volume: 30.000
      face_count: 6
      edge_count: 12
    solid_1:
      volume: 25.000
      face_count: 8
      edge_count: 16
    solid_2:
      volume: 40.000
      face_count: 6
      edge_count: 12
    solid_3:
      volume: 35.000
      face_count: 10
      edge_count: 20
    solid_4:
      volume: 20.000
      face_count: 4
      edge_count: 8
  tags: [assembly]
  metadata:
    part_count: 5
    total_volume: 150.0
```

## 与其他几何体的关系

- **实体 (Solid)**: 复合体的主要组成元素
- **面 (Face)**: 通过实体间接关联
- **边 (Edge)**: 通过实体和面间接关联

## 应用场景

- **装配体建模**: 复杂机械装配
- **建筑设计**: 建筑群体建模
- **产品设计**: 多部件产品
- **制造规划**: 批量生产管理
- **仿真分析**: 多体系统分析

## 管理策略

### 层次化管理
- 使用标签和元数据建立层次结构
- 按功能、材料、工艺等分类
- 实现快速查询和批量操作

### 性能优化
- 合理组织复合体结构
- 避免过深的嵌套层次
- 优化查询和筛选算法

### 数据一致性
- 确保元数据的准确性
- 维护几何体间的关系
- 及时更新统计信息

## 注意事项

- 复合体可能包含大量几何对象，需要注意性能
- 几何对象的修改不会自动更新复合体的统计信息
- 标签和元数据的管理需要建立统一的命名规范
- 复杂的层次结构可能导致查询效率下降
- 需要合理设计数据结构以支持高效的批量操作
- 在进行几何运算时，需要考虑复合体中各对象的相互关系
