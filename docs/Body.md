# Body

## 定义
```python
class Body:
    """三维实体"""
    
    def __init__(self, cq_solid: Any = None)
```

## 描述

Body类表示三维实体对象，是所有三维建模操作的结果。它封装了CADQuery的实体对象，提供统一的接口进行实体操作。

### 核心功能
- 三维实体的创建和管理
- 实体有效性验证
- 面标签系统支持
- 与CADQuery的双向转换

### 面标签功能
面标签（Face Tagging）是Body类的重要功能，允许为实体的各个面添加标识性标签，便于后续的选择和操作。

**核心特性**:
- **自动标签**: 支持立方体、圆柱体、球体等基础几何体的自动面标记
- **手动标签**: 可以为任意面添加自定义标签  
- **多标签支持**: 同一个面可以有多个标签，同一个标签可以标记多个面
- **标签查询**: 快速根据标签名称查找对应的面索引

**标准标签命名**:
- **立方体**: `top`, `bottom`, `front`, `back`, `left`, `right`
- **圆柱体**: `top`, `bottom`, `side`
- **球体**: `surface`

### 主要方法
- `is_valid()`: 检查实体是否有效
- `volume()`: 计算实体体积
- `tag_face(face_index, tag)`: 为指定面添加标签
- `get_faces_by_tag(tag)`: 根据标签获取面索引列表
- `auto_tag_faces(geometry_type)`: 自动为基础几何体的面添加标签

## 示例

### 基础实体创建和验证
```python
from simplecadapi import *

# 创建立方体
box = make_box(10, 5, 3)
print(box)  # Body(id=0, valid=True)
print(f"体积: {box.volume()}")
print(f"是否有效: {box.is_valid()}")

# 创建圆柱体
cylinder = make_cylinder(5, 10)
print(cylinder)  # Body(id=1, valid=True)
```

### 面标签操作
```python
from simplecadapi import *

# 创建立方体并自动标记面
box = make_box(10, 10, 5)
box.auto_tag_faces("box")  # 自动标记立方体的面

# 查看标记的面
print(f"顶面索引: {box.get_faces_by_tag('top')}")
print(f"底面索引: {box.get_faces_by_tag('bottom')}")

# 手动为面添加标签
box.tag_face(0, "special")  # 为第0个面添加特殊标签
print(f"特殊面索引: {box.get_faces_by_tag('special')}")
```

### 布尔运算
```python
from simplecadapi import *

# 创建两个重叠的立方体
box1 = make_box(10, 10, 10)
box2 = make_box(8, 8, 8)

# 布尔并运算
union_result = union(box1, box2)
print(f"并运算结果: {union_result}")

# 布尔减运算
cut_result = cut(box1, box2)
print(f"减运算结果: {cut_result}")
```
