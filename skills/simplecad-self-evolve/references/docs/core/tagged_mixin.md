# TaggedMixin 标签混入类

## 概述

`TaggedMixin` 是 SimpleCAD API 中的标签混入类，为所有几何体类提供统一的标签和元数据管理功能。它是一个混入类（Mixin），被所有核心几何体类继承，实现了标签系统的核心功能。

## 类定义

```python
class TaggedMixin:
    """标签混入类，为几何体提供标签功能"""
```

## 用途

- 为几何体添加标识标签
- 存储和管理元数据
- 实现几何体的分类和查询
- 支持复杂的筛选和批量操作
- 提供几何体的语义信息

## 初始化

### `__init__()`

初始化标签混入类。

**说明:**
- 创建空的标签集合 `_tags`
- 创建空的元数据字典 `_metadata`
- 通常在继承类的 `__init__` 方法中调用

**示例:**
```python
class CustomGeometry(TaggedMixin):
    def __init__(self):
        TaggedMixin.__init__(self)
        # 其他初始化代码
```

## 主要属性

- `_tags`: 标签集合（Set[str]），存储几何体的标签
- `_metadata`: 元数据字典（Dict[str, Any]），存储键值对数据

## 标签管理方法

### `add_tag(tag)`

添加标签到几何体。

**参数:**
- `tag` (str): 要添加的标签名称

**异常:**
- `TypeError`: 当标签不是字符串类型时抛出

**示例:**
```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=5, height=3, depth=2)
box.add_tag("structural")
box.add_tag("main_component")
box.add_tag("steel_part")

print(box.get_tags())  # {'structural', 'main_component', 'steel_part'}
```

### `remove_tag(tag)`

从几何体中移除指定标签。

**参数:**
- `tag` (str): 要移除的标签名称

**说明:**
- 如果标签不存在，不会抛出异常
- 使用 `discard` 方法安全移除

**示例:**
```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=5, height=3, depth=2)
box.add_tag("temporary")
box.add_tag("structural")

box.remove_tag("temporary")
print(box.get_tags())  # {'structural'}

# 移除不存在的标签不会出错
box.remove_tag("nonexistent")
```

### `has_tag(tag)`

检查几何体是否具有指定标签。

**参数:**
- `tag` (str): 要检查的标签名称

**返回:**
- `bool`: 如果具有该标签返回 True，否则返回 False

**示例:**
```python
from simplecadapi import make_cylinder_rsolid

cylinder = make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=5)
cylinder.add_tag("rotational")
cylinder.add_tag("hollow_ready")

if cylinder.has_tag("rotational"):
    print("这是一个旋转体")

if not cylinder.has_tag("solid"):
    cylinder.add_tag("solid")
```

### `get_tags()`

获取几何体的所有标签。

**返回:**
- `Set[str]`: 标签集合的副本

**说明:**
- 返回标签集合的副本，修改返回值不会影响原始标签

**示例:**
```python
from simplecadapi import make_sphere_rsolid

sphere = make_sphere_rsolid(center=(0, 0, 0), radius=1.5)
sphere.add_tag("curved")
sphere.add_tag("symmetric")
sphere.add_tag("smooth")

tags = sphere.get_tags()
print(f"球体标签: {sorted(tags)}")  # ['curved', 'smooth', 'symmetric']

# 修改返回的集合不会影响原始标签
tags.add("new_tag")
print(f"原始标签仍然是: {sorted(sphere.get_tags())}")
```

## 元数据管理方法

### `set_metadata(key, value)`

设置元数据键值对。

**参数:**
- `key` (str): 元数据键名
- `value` (Any): 元数据值，可以是任意类型

**示例:**
```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=5, height=3, depth=2)

# 设置各种类型的元数据
box.set_metadata("material", "aluminum")
box.set_metadata("density", 2.7)
box.set_metadata("cost", 45.50)
box.set_metadata("dimensions", [5, 3, 2])
box.set_metadata("manufactured_date", "2024-01-15")
box.set_metadata("is_finished", True)
box.set_metadata("supplier", {"name": "ABC Corp", "contact": "info@abc.com"})
```

### `get_metadata(key, default=None)`

获取指定键的元数据值。

**参数:**
- `key` (str): 元数据键名
- `default` (Any, 可选): 默认值，当键不存在时返回

**返回:**
- `Any`: 元数据值或默认值

**示例:**
```python
from simplecadapi import make_cylinder_rsolid

cylinder = make_cylinder_rsolid(center=(0, 0, 0), radius=2, height=5)
cylinder.set_metadata("material", "steel")
cylinder.set_metadata("weight", 12.5)

# 获取存在的元数据
material = cylinder.get_metadata("material")
print(f"材料: {material}")  # 材料: steel

weight = cylinder.get_metadata("weight")
print(f"重量: {weight}")  # 重量: 12.5

# 获取不存在的元数据
color = cylinder.get_metadata("color", "default_color")
print(f"颜色: {color}")  # 颜色: default_color

# 不提供默认值时返回 None
surface_finish = cylinder.get_metadata("surface_finish")
print(f"表面处理: {surface_finish}")  # 表面处理: None
```

## 内部辅助方法

### `_format_tags_and_metadata(indent=0)`

格式化标签和元数据的字符串表示。

**参数:**
- `indent` (int): 缩进级别

**返回:**
- `str`: 格式化的字符串

**说明:**
- 内部方法，用于 `__str__` 方法的实现
- 生成美观的标签和元数据显示格式

## 使用示例

### 基础标签使用

```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid, make_sphere_rsolid

def basic_tagging_example():
    """基础标签使用示例"""
    
    # 创建几何体
    box = make_box_rsolid(width=4, height=3, depth=2)
    cylinder = make_cylinder_rsolid(center=(0, 0, 0), radius=1.5, height=4)
    sphere = make_sphere_rsolid(center=(0, 0, 0), radius=1)
    
    # 添加几何类型标签
    box.add_tag("rectangular")
    box.add_tag("prismatic")
    
    cylinder.add_tag("cylindrical")
    cylinder.add_tag("rotational")
    
    sphere.add_tag("spherical")
    sphere.add_tag("curved")
    
    # 添加功能标签
    box.add_tag("structural")
    cylinder.add_tag("pipe")
    sphere.add_tag("bearing")
    
    # 添加材料标签
    for geom in [box, cylinder, sphere]:
        geom.add_tag("metal")
        geom.add_tag("machinable")
    
    # 检查和使用标签
    geometries = [("盒子", box), ("圆柱", cylinder), ("球体", sphere)]
    
    for name, geom in geometries:
        print(f"{name} 标签: {sorted(geom.get_tags())}")
        
        if geom.has_tag("rotational"):
            print(f"  -> {name} 是旋转对称的")
        
        if geom.has_tag("structural"):
            print(f"  -> {name} 用于结构支撑")

basic_tagging_example()
```

### 高级元数据管理

```python
from simplecadapi import make_box_rsolid
import datetime

def advanced_metadata_example():
    """高级元数据管理示例"""
    
    # 创建零件
    part = make_box_rsolid(width=10, height=8, depth=5)
    part.add_tag("machined_part")
    part.add_tag("aluminum")
    
    # 设置基本属性
    part.set_metadata("part_number", "MP-001-A")
    part.set_metadata("revision", "Rev-C")
    part.set_metadata("material", "6061-T6 Aluminum")
    part.set_metadata("density", 2.7)  # g/cm³
    
    # 设置尺寸信息
    dimensions = {
        "length": 10,
        "width": 8,
        "height": 5,
        "tolerance": "±0.1"
    }
    part.set_metadata("dimensions", dimensions)
    
    # 设置制造信息
    manufacturing = {
        "process": "CNC Milling",
        "machine": "Haas VF-2",
        "operator": "John Doe",
        "setup_time": 45,  # minutes
        "cycle_time": 23   # minutes
    }
    part.set_metadata("manufacturing", manufacturing)
    
    # 设置质量控制信息
    quality = {
        "inspection_level": "Level II",
        "critical_dimensions": ["length", "width"],
        "surface_finish": "Ra 1.6 μm",
        "hardness": "HB 95-105"
    }
    part.set_metadata("quality", quality)
    
    # 设置成本信息
    cost_breakdown = {
        "material_cost": 15.50,
        "machining_cost": 45.00,
        "setup_cost": 25.00,
        "overhead": 12.50,
        "total": 98.00
    }
    part.set_metadata("cost", cost_breakdown)
    
    # 设置时间信息
    part.set_metadata("created_date", datetime.datetime.now().isoformat())
    part.set_metadata("due_date", "2024-02-15")
    part.set_metadata("estimated_completion", "2024-02-10")
    
    # 计算衍生属性
    volume = part.get_volume()
    density = part.get_metadata("density")
    weight = volume * density / 1000  # 转换为kg（假设体积单位为cm³）
    
    part.set_metadata("calculated_weight", weight)
    part.set_metadata("weight_unit", "kg")
    
    # 生成报告
    print("零件详细信息报告:")
    print("=" * 50)
    
    # 基本信息
    print(f"零件号: {part.get_metadata('part_number')}")
    print(f"版本: {part.get_metadata('revision')}")
    print(f"材料: {part.get_metadata('material')}")
    print(f"重量: {weight:.3f} kg")
    
    # 尺寸信息
    dims = part.get_metadata("dimensions")
    print(f"\n尺寸:")
    print(f"  长x宽x高: {dims['length']} x {dims['width']} x {dims['height']}")
    print(f"  公差: {dims['tolerance']}")
    
    # 制造信息
    mfg = part.get_metadata("manufacturing")
    print(f"\n制造:")
    print(f"  工艺: {mfg['process']}")
    print(f"  设备: {mfg['machine']}")
    print(f"  周期时间: {mfg['cycle_time']} 分钟")
    
    # 成本信息
    cost = part.get_metadata("cost")
    print(f"\n成本:")
    print(f"  材料: ${cost['material_cost']:.2f}")
    print(f"  加工: ${cost['machining_cost']:.2f}")
    print(f"  总计: ${cost['total']:.2f}")
    
    return part

advanced_part = advanced_metadata_example()
```

### 批量标签和元数据操作

```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid

def batch_tagging_example():
    """批量标签和元数据操作示例"""
    
    # 创建零件集合
    parts = []
    
    # 创建不同类型的零件
    part_specs = [
        ("housing", "box", (10, 8, 6), "aluminum"),
        ("shaft", "cylinder", (1, 15), "steel"),
        ("bracket", "box", (5, 3, 2), "aluminum"),
        ("bushing", "cylinder", (0.5, 3), "bronze"),
        ("plate", "box", (8, 6, 0.5), "steel")
    ]
    
    for name, shape_type, dimensions, material in part_specs:
        if shape_type == "box":
            part = make_box_rsolid(width=dimensions[0], height=dimensions[1], depth=dimensions[2])
        else:  # cylinder
            part = make_cylinder_rsolid(center=(0, 0, 0), radius=dimensions[0], height=dimensions[1])
        
        # 基本标签
        part.add_tag(name)
        part.add_tag(shape_type)
        part.add_tag(material)
        
        # 基本元数据
        part.set_metadata("name", name)
        part.set_metadata("material", material)
        part.set_metadata("shape_type", shape_type)
        
        parts.append(part)
    
    # 批量添加通用标签
    for part in parts:
        part.add_tag("mechanical_part")
        part.add_tag("machined")
        part.set_metadata("project", "Assembly_001")
        part.set_metadata("status", "design")
    
    # 根据材料批量设置属性
    material_properties = {
        "aluminum": {"density": 2.7, "cost_per_kg": 3.50, "color": "silver"},
        "steel": {"density": 7.8, "cost_per_kg": 1.20, "color": "gray"},
        "bronze": {"density": 8.9, "cost_per_kg": 8.50, "color": "bronze"}
    }
    
    for part in parts:
        material = part.get_metadata("material")
        if material in material_properties:
            props = material_properties[material]
            for prop_name, prop_value in props.items():
                part.set_metadata(prop_name, prop_value)
    
    # 根据尺寸批量分类
    for part in parts:
        volume = part.get_volume()
        
        if volume < 10:
            part.add_tag("small_part")
            part.set_metadata("size_category", "small")
        elif volume < 100:
            part.add_tag("medium_part")
            part.set_metadata("size_category", "medium")
        else:
            part.add_tag("large_part")
            part.set_metadata("size_category", "large")
    
    # 批量计算成本
    for part in parts:
        volume = part.get_volume()
        density = part.get_metadata("density", 1.0)
        cost_per_kg = part.get_metadata("cost_per_kg", 2.0)
        
        weight = volume * density / 1000  # 转换为kg
        material_cost = weight * cost_per_kg
        
        part.set_metadata("weight", weight)
        part.set_metadata("material_cost", material_cost)
    
    # 批量查询和统计
    print("批量操作结果:")
    print("=" * 40)
    
    # 按材料统计
    materials = set(p.get_metadata("material") for p in parts)
    for material in materials:
        material_parts = [p for p in parts if p.get_metadata("material") == material]
        total_weight = sum(p.get_metadata("weight", 0) for p in material_parts)
        total_cost = sum(p.get_metadata("material_cost", 0) for p in material_parts)
        
        print(f"{material.upper()} 零件:")
        print(f"  数量: {len(material_parts)}")
        print(f"  总重量: {total_weight:.3f} kg")
        print(f"  材料成本: ${total_cost:.2f}")
        print()
    
    # 按尺寸分类统计
    size_categories = ["small", "medium", "large"]
    for size in size_categories:
        size_parts = [p for p in parts if p.has_tag(f"{size}_part")]
        if size_parts:
            avg_volume = sum(p.get_volume() for p in size_parts) / len(size_parts)
            print(f"{size.upper()} 零件: {len(size_parts)} 个, 平均体积: {avg_volume:.3f}")
    
    return parts

batch_parts = batch_tagging_example()
```

### 高级查询和筛选

```python
from simplecadapi import make_box_rsolid, make_cylinder_rsolid, make_sphere_rsolid

def advanced_query_example():
    """高级查询和筛选示例"""
    
    # 创建复杂的零件库
    parts_library = []
    
    # 定义零件类型
    part_definitions = [
        # (name, shape, dimensions, material, application, priority)
        ("main_frame", "box", (20, 15, 10), "steel", "structural", "high"),
        ("support_beam", "box", (15, 5, 5), "aluminum", "structural", "medium"),
        ("motor_shaft", "cylinder", (2, 25), "steel", "rotating", "high"),
        ("bearing_housing", "cylinder", (3, 8), "aluminum", "support", "medium"),
        ("control_sphere", "sphere", (2,), "plastic", "interface", "low"),
        ("sensor_mount", "box", (3, 3, 2), "aluminum", "mounting", "medium"),
        ("drive_wheel", "cylinder", (5, 3), "rubber", "motion", "high"),
        ("safety_cover", "box", (12, 8, 1), "plastic", "protection", "low")
    ]
    
    for name, shape, dims, material, application, priority in part_definitions:
        # 创建几何体
        if shape == "box":
            part = make_box_rsolid(width=dims[0], height=dims[1], depth=dims[2])
        elif shape == "cylinder":
            part = make_cylinder_rsolid(center=(0, 0, 0), radius=dims[0], height=dims[1])
        else:  # sphere
            part = make_sphere_rsolid(center=(0, 0, 0), radius=dims[0])
        
        # 添加标签
        part.add_tag(name)
        part.add_tag(shape)
        part.add_tag(material)
        part.add_tag(application)
        part.add_tag(priority)
        
        # 设置详细元数据
        part.set_metadata("name", name)
        part.set_metadata("shape", shape)
        part.set_metadata("material", material)
        part.set_metadata("application", application)
        part.set_metadata("priority", priority)
        part.set_metadata("volume", part.get_volume())
        
        # 根据应用设置其他属性
        if application == "structural":
            part.add_tag("load_bearing")
            part.set_metadata("safety_factor", 2.5)
        elif application == "rotating":
            part.add_tag("dynamic")
            part.set_metadata("max_rpm", 3600)
        elif application == "interface":
            part.add_tag("user_contact")
            part.set_metadata("ergonomic", True)
        
        # 根据材料设置属性
        material_db = {
            "steel": {"density": 7.8, "strength": "high", "cost": 1.2},
            "aluminum": {"density": 2.7, "strength": "medium", "cost": 3.5},
            "plastic": {"density": 1.2, "strength": "low", "cost": 0.8},
            "rubber": {"density": 1.5, "strength": "flexible", "cost": 2.0}
        }
        
        if material in material_db:
            for prop, value in material_db[material].items():
                part.set_metadata(prop, value)
        
        parts_library.append(part)
    
    # 定义查询函数
    def query_parts(parts, **criteria):
        """根据条件查询零件"""
        result = parts
        
        for key, value in criteria.items():
            if key == "has_tag":
                result = [p for p in result if p.has_tag(value)]
            elif key == "has_any_tag":
                result = [p for p in result if any(p.has_tag(tag) for tag in value)]
            elif key == "has_all_tags":
                result = [p for p in result if all(p.has_tag(tag) for tag in value)]
            elif key == "metadata_equals":
                meta_key, meta_value = value
                result = [p for p in result if p.get_metadata(meta_key) == meta_value]
            elif key == "metadata_greater":
                meta_key, threshold = value
                result = [p for p in result if p.get_metadata(meta_key, 0) > threshold]
            elif key == "metadata_less":
                meta_key, threshold = value
                result = [p for p in result if p.get_metadata(meta_key, float('inf')) < threshold]
            elif key == "volume_range":
                min_vol, max_vol = value
                result = [p for p in result if min_vol <= p.get_volume() <= max_vol]
        
        return result
    
    # 执行各种查询
    print("高级查询示例:")
    print("=" * 50)
    
    # 1. 简单标签查询
    steel_parts = query_parts(parts_library, has_tag="steel")
    print(f"1. 钢制零件: {len(steel_parts)} 个")
    for part in steel_parts:
        print(f"   - {part.get_metadata('name')}")
    
    # 2. 多标签查询
    structural_aluminum = query_parts(parts_library, has_all_tags=["aluminum", "structural"])
    print(f"\n2. 铝制结构件: {len(structural_aluminum)} 个")
    
    # 3. 元数据查询
    high_priority = query_parts(parts_library, metadata_equals=("priority", "high"))
    print(f"\n3. 高优先级零件: {len(high_priority)} 个")
    for part in high_priority:
        print(f"   - {part.get_metadata('name')}: {part.get_metadata('application')}")
    
    # 4. 范围查询
    large_parts = query_parts(parts_library, volume_range=(100, 5000))
    print(f"\n4. 大型零件 (体积 100-5000): {len(large_parts)} 个")
    
    # 5. 复合查询
    critical_metal_parts = query_parts(
        parts_library,
        has_any_tag=["steel", "aluminum"],
        metadata_equals=("priority", "high")
    )
    print(f"\n5. 关键金属零件: {len(critical_metal_parts)} 个")
    
    # 6. 性能分析查询
    load_bearing = query_parts(parts_library, has_tag="load_bearing")
    if load_bearing:
        avg_safety_factor = sum(p.get_metadata("safety_factor", 1) for p in load_bearing) / len(load_bearing)
        print(f"\n6. 承载零件平均安全系数: {avg_safety_factor:.2f}")
    
    # 7. 成本分析
    total_cost = 0
    cost_by_material = {}
    
    for part in parts_library:
        volume = part.get_volume()
        density = part.get_metadata("density", 1)
        cost_per_kg = part.get_metadata("cost", 1)
        
        weight = volume * density / 1000
        cost = weight * cost_per_kg
        total_cost += cost
        
        material = part.get_metadata("material")
        if material not in cost_by_material:
            cost_by_material[material] = 0
        cost_by_material[material] += cost
    
    print(f"\n7. 成本分析:")
    print(f"   总成本: ${total_cost:.2f}")
    for material, cost in cost_by_material.items():
        print(f"   {material}: ${cost:.2f}")
    
    return parts_library

parts_db = advanced_query_example()
```

## 最佳实践

### 标签命名规范

1. **一致性**: 使用一致的命名风格
2. **层次化**: 使用点号分隔的层次结构（如 `material.metal.steel`）
3. **描述性**: 标签名称应该具有描述性
4. **避免空格**: 使用下划线代替空格

### 元数据组织

1. **结构化**: 使用字典组织相关的元数据
2. **类型一致**: 相同用途的元数据使用相同的数据类型
3. **单位明确**: 数值型元数据要明确单位
4. **版本控制**: 重要元数据要包含版本信息

### 性能考虑

1. **标签数量**: 避免过多的标签，影响查询性能
2. **元数据大小**: 避免存储大型数据对象
3. **查询优化**: 合理组织标签和元数据以支持高效查询
4. **内存管理**: 及时清理不需要的标签和元数据

## 注意事项

- 标签必须是字符串类型
- 标签区分大小写
- 元数据值可以是任意类型，但建议使用可序列化的类型
- 标签和元数据的修改不会触发几何体的更新
- 在进行深拷贝时，需要特别处理标签和元数据
- 标签和元数据不参与几何运算，仅用于管理和查询
