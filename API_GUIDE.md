# SimpleCAD API 使用指南

SimpleCAD API 是一个基于 CADQuery 的简化 CAD 建模 Python API，提供直观易用的几何建模接口。

## 安装

确保已安装 CADQuery：

```bash
pip install cadquery
```

## 快速开始

### 基本几何体创建

```python
import simplecadapi as scad

# 创建基本几何体
point = scad.create_point(0, 0, 0)
line = scad.create_line((0, 0, 0), (1, 0, 0))
circle = scad.create_circle_face((0, 0, 0), 1.0)
rectangle = scad.create_rectangle_face(2.0, 1.0)
box = scad.create_box(1.0, 1.0, 1.0)
cylinder = scad.create_cylinder(0.5, 2.0)
sphere = scad.create_sphere(1.0)
```

### 变换操作

```python
# 平移
translated = scad.translate(box, (1, 0, 0))

# 旋转（角度使用弧度）
rotated = scad.rotate(box, 3.14159/4, (0, 0, 1))  # 绕Z轴旋转45度
```

### 3D操作

```python
# 拉伸
profile = scad.create_rectangle_face(2.0, 1.0)
extruded = scad.extrude(profile, (0, 0, 1), 2.0)

# 旋转成型
revolved = scad.revolve(profile, (0, 0, 1), 3.14159)  # 旋转180度
```

### 布尔运算

```python
box1 = scad.create_box(2.0, 2.0, 2.0)
box2 = scad.create_box(1.0, 1.0, 3.0, center=(0.5, 0.5, 0))

# 并集
union_result = scad.union(box1, box2)

# 差集
cut_result = scad.cut(box1, box2)

# 交集
intersect_result = scad.intersect(box1, box2)
```

### 标签系统

```python
# 设置标签
scad.set_tag(box, "main_body")

# 检查标签
if box.has_tag("main_body"):
    print("找到标签")

# 自动标记面
box.auto_tag_faces("box")  # 为立方体的面自动添加top, bottom, front等标签

# 根据标签选择面
top_faces = scad.select_faces_by_tag(box, "top")
```

### 工作平面

```python
# 使用工作平面定义局部坐标系
with scad.Workplane(origin=(5, 0, 0)):
    local_box = scad.create_box(1, 1, 1)  # 在(5,0,0)位置创建

# 嵌套工作平面
with scad.Workplane(origin=(2, 0, 0)):
    with scad.Workplane(origin=(1, 1, 0)):
        nested_box = scad.create_box(0.5, 0.5, 0.5)  # 在(3,1,0)位置创建
```

### 导出

```python
# 导出为STL格式
scad.to_stl(box, "output.stl")

# 导出为STEP格式
scad.to_step(box, "output.step")

# 导出多个几何体
scad.to_stl([box1, box2, box3], "multiple_objects.stl")
```

## API 命名规范

SimpleCAD API 使用清晰的命名规范：

- 所有函数名使用 snake_case
- 函数名以动词开头，表示操作类型
- 函数名包含返回类型后缀，例如：
  - `make_circle_redge` - 创建圆并返回边(Edge)
  - `make_circle_rwire` - 创建圆并返回线(Wire)  
  - `make_circle_rface` - 创建圆并返回面(Face)
  - `make_box_rsolid` - 创建立方体并返回实体(Solid)

## 核心类型

### 几何体类型
- `Vertex` - 顶点
- `Edge` - 边
- `Wire` - 线（边的集合）
- `Face` - 面
- `Shell` - 壳（面的集合）
- `Solid` - 实体
- `Compound` - 复合体

### 坐标系类型
- `CoordinateSystem` - 三维坐标系
- `Workplane` - 工作平面（上下文管理器）

## 高级功能

### 样条曲线

```python
# 创建样条曲线
points = [(0.0, 0.0, 0.0), (2.0, 1.0, 0.0), (4.0, 0.0, 0.0)]
spline = scad.create_spline(points)
```

### 三点圆弧

```python
# 通过三个点创建圆弧
arc = scad.create_arc((0, 0, 0), (1, 1, 0), (2, 0, 0))
```

### 复杂示例

```python
# 创建带孔的零件
def create_bracket():
    # 主体
    base = scad.create_box(10, 5, 2)
    
    # 孔
    hole1 = scad.create_cylinder(1, 3, center=(2, 0, 0))
    hole2 = scad.create_cylinder(1, 3, center=(8, 0, 0))
    
    # 组合
    bracket = scad.cut(base, hole1)
    bracket = scad.cut(bracket, hole2)
    
    # 添加标签
    scad.set_tag(bracket, "bracket")
    
    return bracket

bracket = create_bracket()
scad.to_step(bracket, "bracket.step")
```

## 错误处理

所有 API 函数都包含详细的错误处理和异常信息：

```python
try:
    box = scad.create_box(-1, 1, 1)  # 负数尺寸会引发错误
except ValueError as e:
    print(f"创建失败: {e}")
```

## 扩展原则

SimpleCAD API 遵循开放封闭原则：

- 核心类型是封闭的，不应修改
- 所有新功能通过创建新函数实现
- 可以组合现有函数创建更复杂的操作

### 自定义函数示例

```python
def create_gear(outer_radius, inner_radius, height, num_teeth):
    """创建简化的齿轮"""
    # 基础圆盘
    base = scad.create_cylinder(outer_radius, height)
    
    # 中心孔
    hole = scad.create_cylinder(inner_radius, height * 1.1)
    gear = scad.cut(base, hole)
    
    # 添加齿（简化版本）
    import math
    for i in range(num_teeth):
        angle = 2 * math.pi * i / num_teeth
        x = (outer_radius - 0.2) * math.cos(angle)
        y = (outer_radius - 0.2) * math.sin(angle)
        
        tooth = scad.create_box(0.3, 0.1, height, center=(x, y, height/2))
        gear = scad.union(gear, tooth)
    
    return gear

# 使用自定义函数
my_gear = create_gear(5, 1, 1, 12)
scad.to_stl(my_gear, "my_gear.stl")
```

## 注意事项

1. **坐标系**: SimpleCAD 使用 Z 向上的右手坐标系
2. **角度单位**: 所有角度参数使用弧度，不是角度
3. **尺寸单位**: 默认单位是毫米（与 CADQuery 一致）
4. **内存管理**: 大型模型可能消耗较多内存，建议及时释放不需要的对象

## 性能提示

1. 避免在循环中创建大量临时对象
2. 使用标签系统来管理复杂模型的组件
3. 考虑将复杂操作分解为简单步骤
4. 导出大型模型时可能需要较长时间

## 更多示例

查看 `examples.py` 文件获取更多高级用法示例，包括：
- 复杂零件建模
- 工作平面使用
- 样条曲线应用
- 类似齿轮的形状创建
- 变换操作演示
