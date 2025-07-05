# CAD建模形式化Python API设计与实现
---
## 简介

本项目旨在使用CadQuery的occ impl.shapes中提供的方法，编写一套命令式的Python API，以简化通过代码进行CAD建模的过程。API设计遵循开放封闭原则，核心类型封闭，所有的操作和扩展都通过新建函数实现。
同时兼容Numpy库，允许用户在几何体上进行高效的数学运算和变换。

## 基础类型

### 图元类型
 
图元类型和OCP的TopoDS_Shape类型一一对应，主要包括以下几种：
- `Solid`: 实体类型，表示封闭的三维几何体。
- `Shell`: 壳体类型，表示封闭的表面集合。
- `Face`: 面类型，表示单个表面。
- `Edge`: 边类型，表示曲线边界。
- `Vertex`: 顶点类型，表示几何体的点。
- `Wire`: 线类型，表示边的集合。

### 坐标系类型
坐标系类型用于定义三维空间中的位置和方向，我们对于世界坐标系的定义是：一个右手坐标系，原点在(0, 0, 0)，默认X轴向前，Y轴向右，Z轴向上。坐标系类型包括：
- `Workplane`: 工作平面类型，表示一个二维平面，本质上统计一个原点和一个法向量和一个X轴方向向量。作为一个上下文变量，可以通过with语法包裹操作，那么这些操作就会在这个工作平面下进行。允许嵌套定义Workplane，那么嵌套定义的平面将在上一个平面的基础上进行变换。

## 支持的操作和特性

1. 变换：
   - 平移：`translate(Shape, vector)`
   - 旋转：`rotate(Shape, angle, axis, origin)`
   - 缩放：`scale(Shape, factor, origin)`

2. 基础和高级Edge，Wire，Face，Shell，Solid创建：

 - 针对Edge和Wire
  
     - Segment
     - AngleArc
     - ThreePointArc
     - Spline
     - Polyline
     - Helix
  
  - 针对Edge，Wire和Face：
  
     - Rect
     - Circle
     - Ellipse
     - Triangle
     - Polygon
  
  - 针对Shell和Solid：
     
     - Box
     - Cylinder
     - Sphere
     - Cone
     - Torus
     - Prism
     - Wedge


3. 元素自动与手动tag与tag选择

  - 例如：我们可以在创建几何元素的时候手动设置标签，例如`set_tag(Shape, "my_tag")`

    - 针对操作产生的新几何体需要有自动tag 策略，例如通过extrude一个rect得到的Solid，其中的边如果没有标签，会根据当的坐标系上下文得到的边位置和面法相信息，自动打上tag， 例如"top_edge_1", "bottom_edge_1", "front_face"等。

  - 或者在创建后通过`select_edge_by_tag(Shape, "my_tag")` 或者 `select_face_by_tag(Shape, "my_tag")`来选择所有带有特定标签的元素


4. 特征与3D操作

  - Fillet
  - Chamfer
  - Mirror
  - Shell
  - Loft
  - Sweep
  - Linear/2D/Radial Pattern
  - Extrude
  - Revolve
  - Helical Sweep

  - 需要选择边或者面进行操作的特征操作，例如Fillet和Chamfer，可以通过`select_edge_by_tag(Shape, "my_tag")`来选择特定的边进行操作。
  - 对于shell等，可以通过tag选择面来实现抽壳同时去除面。


4. 几何体布尔运算

   - Union：`union(Shape1, Shape2)`
   - Cut：`cut(Shape1, Shape2)`
   - Intersection：`intersection(Shape1, Shape2)`
  

## API命名风格
- 所有函数名使用小写字母和下划线分隔（snake_case），要求使用动词开头，表示操作或行为，同时需要包含API的返回类型(因为同名API可能会重载为返回不同类型的对象，但我们想要避免这一点)，例如：`make_circle_rwire`, `make_circle_redge`, `make_circle_rface`, `extrude_rsolid`等
- 类名使用驼峰命名法（CamelCase）
- 函数和类的文档字符串使用Google风格，包含参数、返回值和异常说明
- 所有函数和类都应有类型注解，确保代码的可读性和可维护性
- 所有函数和类都应有详细的文档字符串，描述其功能、参数、返回值和异常
- 所有函数和类都应有示例代码，便于用户理解和使用
- 所有的代码实现都要有严格且详细的try catch和异常抛出，异常抛出的内容中要求明确指出错误原因，以及用户应当如何在调用层做出怎样的改进可能可以避免这个问题。


## 扩展原则

开放封闭原则，核心类型封闭，所有的操作和扩展都通过新建函数实现。我们可以通过利用现有的函数和操作来组合出新的高级操作并封装为函数来实现功能的扩展。


