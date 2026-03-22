# TaggedMixin

## Overview

`TaggedMixin` is the tag mixin class in SimpleCAD API, providing unified tag and metadata management functionality for all geometry classes. It is a mixin class inherited by all core geometry classes, implementing the core functionality of the tag system.

## Class Definition

```python
class TaggedMixin:
    """标签混入类，为几何体提供标签功能"""
```

## Usage

- Add identification tags to geometries
- Store and manage metadata
- Implement geometry classification and queries
- Support complex filtering and batch operations
- Provide semantic information for geometries

## Initialization

### `__init__()`

Initialize the tag mixin class.

**Description:**
- Creates an empty tag set `_tags`
- Creates an empty metadata dictionary `_metadata`
- Usually called in the `__init__` method of inheriting classes

**Example:**
```python
class CustomGeometry(TaggedMixin):
    def __init__(self):
        TaggedMixin.__init__(self)
        # 其他初始化代码
```

## Main Properties

- `_tags`: Tag set (Set[str]), storing geometry tags
- `_metadata`: Metadata dictionary (Dict[str, Any]), storing key-value pairs

## Tag Management Methods

### `add_tag(tag)`

Add a tag to the geometry.

**Parameters:**
- `tag` (str): Name of the tag to add

**Exceptions:**
- `TypeError`: Raised when the tag is not a string type

**Example:**
```python
from simplecadapi import make_box_rsolid

box = make_box_rsolid(width=5, height=3, depth=2)
box.add_tag("structural")
box.add_tag("main_component")
box.add_tag("steel_part")

print(box.get_tags())  # {'structural', 'main_component', 'steel_part'}
```

### `remove_tag(tag)`

Remove a specified tag from the geometry.

**Parameters:**
- `tag` (str): Name of the tag to remove

**Description:**
- If the tag does not exist, no exception will be raised
- Uses the `discard` method for safe removal

**Example:**
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

Check if the geometry has a specified tag.

**Parameters:**
- `tag` (str): Name of the tag to check

**Returns:**
- `bool`: Returns True if the tag exists, False otherwise

**Example:**
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

Get all tags of the geometry.

**Returns:**
- `Set[str]`: A copy of the tag set

**Description:**
- Returns a copy of the tag set; modifying the return value will not affect the original tags

**Example:**
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

## Metadata Management Methods

### `set_metadata(key, value)`

Set a metadata key-value pair.

**Parameters:**
- `key` (str): Metadata key name
- `value` (Any): Metadata value, can be any type

**Example:**
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

Get the metadata value for a specified key.

**Parameters:**
- `key` (str): Metadata key name
- `default` (Any, optional): Default value, returned when the key does not exist

**Returns:**
- `Any`: Metadata value or default value

**Example:**
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

## Internal Helper Methods

### `_format_tags_and_metadata(indent=0)`

Format the string representation of tags and metadata.

**Parameters:**
- `indent` (int): Indentation level

**Returns:**
- `str`: Formatted string

**Description:**
- Internal method, used for implementing `__str__` method
- Generates aesthetically pleasing tag and metadata display format

## Usage Examples

### Basic Tag Usage

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

### Advanced Metadata Management

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

### Batch Tag and Metadata Operations

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

### Advanced Query and Filtering

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

## Best Practices

### Tag Naming Conventions

1. **Consistency**: Use consistent naming styles
2. **Hierarchy**: Use dot-separated hierarchical structures (e.g., `material.metal.steel`)
3. **Descriptive**: Tag names should be descriptive
4. **Avoid Spaces**: Use underscores instead of spaces

### Metadata Organization

1. **Structured**: Use dictionaries to organize related metadata
2. **Type Consistency**: Use the same data type for metadata with similar purposes
3. **Clear Units**: Numerical metadata should specify units
4. **Version Control**: Important metadata should include version information

### Performance Considerations

1. **Tag Quantity**: Avoid excessive tags that may impact query performance
2. **Metadata Size**: Avoid storing large data objects
3. **Query Optimization**: Organize tags and metadata appropriately to support efficient queries
4. **Memory Management**: Clean up unnecessary tags and metadata in a timely manner

## Notes

- Tags must be of string type
- Tags are case-sensitive
- Metadata values can be of any type, but serializable types are recommended
- Tag and metadata modifications do not trigger geometry updates
- Special handling is required for tags and metadata during deep copying
- Tags and metadata do not participate in geometric operations; they are only used for management and queries
