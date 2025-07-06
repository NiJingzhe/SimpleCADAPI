# SimpleCAD API 核心类文档

本目录包含 SimpleCAD API 所有核心类的详细文档。

## 核心类概览

SimpleCAD API 提供了一套完整的几何建模类，从基础的点线面到复杂的实体和复合体，每个类都具有丰富的功能和灵活的标签管理系统。

### 基础类

#### [CoordinateSystem - 坐标系](coordinate_system.md)
三维坐标系类，用于定义和管理局部坐标系，支持坐标转换和与 CADQuery 的集成。

**主要功能:**
- 定义局部坐标系
- 坐标和向量转换
- 与 CADQuery 坐标系转换

#### [SimpleWorkplane - 工作平面](simple_workplane.md)
工作平面上下文管理器，提供局部坐标系环境，支持嵌套使用。

**主要功能:**
- 定义工作平面
- 上下文管理器支持
- 嵌套坐标系管理

#### [TaggedMixin - 标签混入类](tagged_mixin.md)
为所有几何体提供统一的标签和元数据管理功能的混入类。

**主要功能:**
- 标签管理（添加、删除、查询）
- 元数据存储和检索
- 几何体分类和查询支持

### 几何体类

#### 0维几何体

##### [Vertex - 顶点](vertex.md)
表示三维空间中的点，是所有几何体的基础元素。

**主要功能:**
- 存储三维坐标
- 标签和元数据管理
- 坐标查询

#### 1维几何体

##### [Edge - 边](edge.md)
表示连接两个顶点的一维几何元素，可以是直线、圆弧、样条等。

**主要功能:**
- 长度计算
- 端点查询
- 几何类型识别

##### [Wire - 线](wire.md)
由多个边连接而成的一维几何路径，可以是开放或闭合的。

**主要功能:**
- 边集合管理
- 闭合性检查
- 路径分析

#### 2维几何体

##### [Face - 面](face.md)
表示二维表面几何，由一个或多个线围成，可以包含孔洞。

**主要功能:**
- 面积计算
- 法向量查询
- 边界线管理

##### [Shell - 壳](shell.md)
由多个面组成的表面集合，可以是开放或闭合的。

**主要功能:**
- 面集合管理
- 表面分析
- 薄壁结构支持

#### 3维几何体

##### [Solid - 实体](solid.md)
表示三维封闭几何体，具有体积，是 CAD 建模的核心对象。

**主要功能:**
- 体积计算
- 面和边查询
- 自动面标记
- 布尔运算支持

##### [Compound - 复合体](compound.md)
由多个几何对象组成的集合，用于管理复杂装配体。

**主要功能:**
- 多实体管理
- 层次结构支持
- 批量操作

## 类关系图

```
TaggedMixin
├── Vertex (0D)
├── Edge (1D)
├── Wire (1D) ← composed of Edges
├── Face (2D) ← bounded by Wires
├── Shell (2D) ← collection of Faces
├── Solid (3D) ← bounded by Shells/Faces
└── Compound (3D) ← collection of Solids

CoordinateSystem ← independent utility class
SimpleWorkplane ← uses CoordinateSystem
```

## 继承关系

所有几何体类都继承自 `TaggedMixin`，获得统一的标签和元数据管理功能：

- **标签系统**: 为几何体添加字符串标签，支持分类和查询
- **元数据系统**: 存储键值对数据，支持复杂的属性管理
- **查询支持**: 基于标签和元数据的高效查询和筛选

## 坐标系统

SimpleCAD 使用统一的坐标系统：

- **全局坐标系**: Z向上的右手坐标系
- **局部坐标系**: 通过 `CoordinateSystem` 和 `SimpleWorkplane` 定义
- **CADQuery兼容**: 自动处理与 CADQuery 坐标系的转换

## 设计原则

### 一致性
所有类都遵循相同的设计模式和命名约定，提供一致的用户体验。

### 可扩展性
通过标签和元数据系统，用户可以为几何体添加自定义信息，支持复杂的应用场景。

### 互操作性
与 CADQuery 无缝集成，可以充分利用 CADQuery 的强大功能。

### 易用性
提供直观的 API 和丰富的示例，降低学习成本。

## 使用指南

### 基础使用流程

1. **创建几何体**: 使用 `make_*` 函数创建基础几何体
2. **添加标签**: 使用 `add_tag()` 为几何体添加标识
3. **设置元数据**: 使用 `set_metadata()` 存储属性信息
4. **组合操作**: 使用布尔运算、变换等操作创建复杂几何体
5. **查询筛选**: 基于标签和元数据查询所需的几何体

### 最佳实践

1. **标签命名**: 使用一致的命名规范，如 `category.subcategory.detail`
2. **元数据组织**: 使用结构化的数据组织相关信息
3. **坐标系管理**: 合理使用工作平面简化复杂几何的创建
4. **性能考虑**: 避免过多的标签和大型元数据影响性能

## 示例代码

```python
from simplecadapi import *

# 创建工作平面
with SimpleWorkplane(origin=(0, 0, 0)) as wp:
    # 创建基础几何体
    box = make_box_rsolid(width=5, height=3, depth=2)
    
    # 添加标签和元数据
    box.add_tag("structural")
    box.add_tag("aluminum")
    box.set_metadata("material", "6061-T6")
    box.set_metadata("density", 2.7)
    
    # 自动标记面
    box.auto_tag_faces("box")
    
    # 查询特定面
    top_faces = [f for f in box.get_faces() if f.has_tag("top")]
```

## 扩展开发

如果需要创建自定义几何体类：

1. 继承 `TaggedMixin` 获得标签功能
2. 包装相应的 CADQuery 对象
3. 实现必要的几何查询方法
4. 提供适当的字符串表示方法

```python
class CustomGeometry(TaggedMixin):
    def __init__(self, cq_object):
        TaggedMixin.__init__(self)
        self.cq_object = cq_object
    
    def get_custom_property(self):
        # 实现自定义功能
        pass
```

## 更多资源

- [API参考文档](../api/)
- [示例代码](../../examples.py)
- [用户指南](../../README.md)
