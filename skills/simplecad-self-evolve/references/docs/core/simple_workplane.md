# SimpleWorkplane 工作平面

## 概述

`SimpleWorkplane` 是 SimpleCAD API 中的工作平面类，用于定义局部坐标系和几何建模的工作平面。它支持嵌套使用，可以作为上下文管理器，为几何操作提供局部坐标系环境。

## 类定义

```python
class SimpleWorkplane:
    """工作平面上下文管理器
    
    用于定义局部坐标系，支持嵌套使用
    """
```

## 用途

- 定义局部工作平面
- 提供上下文管理器功能, 使用with语句自动管理坐标系
- 支持嵌套坐标系
- 与 CADQuery Workplane 的转换
- 简化复杂几何的建模

## 构造函数

### `__init__(origin, normal, x_dir)`

初始化工作平面。

**参数:**
- `origin` (Tuple[float, float, float], 可选): 工作平面原点，默认 (0, 0, 0)
- `normal` (Tuple[float, float, float], 可选): 工作平面法向量，默认 (0, 0, 1)
- `x_dir` (Tuple[float, float, float], 可选): 工作平面X轴方向，默认 (1, 0, 0)

**示例:**
```python
from simplecadapi import SimpleWorkplane

# 默认工作平面（XY平面）
wp = SimpleWorkplane()

# 自定义工作平面
wp = SimpleWorkplane(
    origin=(0, 0, 5),
    normal=(0, 0, 1),
    x_dir=(1, 0, 0)
)

# 倾斜的工作平面
wp = SimpleWorkplane(
    origin=(0, 0, 0),
    normal=(0, 1, 1),  # 45度倾斜
    x_dir=(1, 0, 0)
)
```

## 主要属性

- `cs`: 工作平面对应的坐标系 (CoordinateSystem)
- `cq_workplane`: CADQuery 工作平面对象（懒加载）

## 常用方法

### 上下文管理器方法

SimpleWorkplane 支持 `with` 语句，在上下文中自动管理当前坐标系。

**示例:**
```python
from simplecadapi import SimpleWorkplane, make_box_rsolid

# 在全局坐标系中创建盒子
box1 = make_box_rsolid(1, 1, 1)

# 在局部坐标系中创建盒子
with SimpleWorkplane(origin=(2, 0, 0)) as wp:
    box2 = make_box_rsolid(1, 1, 1)  # 实际位置在 (2, 0, 0)
```


### `to_cq_workplane()`

转换为 CADQuery 的 Workplane 对象。

**返回:**
- `cadquery.Workplane`: CADQuery 工作平面对象

**示例:**
```python
from simplecadapi import SimpleWorkplane

wp = SimpleWorkplane(origin=(0, 0, 1))
cq_wp = wp.to_cq_workplane()
```
## 使用示例

### 基本使用

```python
from simplecadapi import SimpleWorkplane, make_circle_rface, extrude_rsolid

# 创建工作平面
wp = SimpleWorkplane(origin=(0, 0, 0), normal=(0, 0, 1))

# 使用工作平面
with wp:
    # 在工作平面上创建圆形面
    circle = make_circle_rface(radius=1.0)
    
    # 拉伸成圆柱体
    cylinder = extrude_rsolid(circle, height=2.0)
```

### 嵌套工作平面

```python
from simplecadapi import SimpleWorkplane, make_box_rsolid

# 第一层工作平面
with SimpleWorkplane(origin=(1, 0, 0)) as wp1:
    box1 = make_box_rsolid(1, 1, 1)  # 位置在 (1, 0, 0)
    
    # 第二层工作平面（相对于第一层）
    with SimpleWorkplane(origin=(0, 1, 0)) as wp2:
        box2 = make_box_rsolid(1, 1, 1)  # 位置在 (1, 1, 0)
        
        # 第三层工作平面（相对于第二层）
        with SimpleWorkplane(origin=(0, 0, 1)) as wp3:
            box3 = make_box_rsolid(1, 1, 1)  # 位置在 (1, 1, 1)
```

### 创建复杂几何

```python
from simplecadapi import SimpleWorkplane, make_rectangle_rface, extrude_rsolid

# 创建一个带有多个特征的零件
def create_complex_part():
    parts = []
    
    # 主体
    with SimpleWorkplane(origin=(0, 0, 0)) as wp:
        base = make_rectangle_rface(width=10, height=5)
        main_body = extrude_rsolid(base, height=2)
        parts.append(main_body)
    
    # 左侧支架
    with SimpleWorkplane(origin=(-3, 0, 2), normal=(1, 0, 0)) as wp:
        bracket = make_rectangle_rface(width=3, height=2)
        left_bracket = extrude_rsolid(bracket, height=1)
        parts.append(left_bracket)
    
    # 右侧支架
    with SimpleWorkplane(origin=(3, 0, 2), normal=(-1, 0, 0)) as wp:
        bracket = make_rectangle_rface(width=3, height=2)
        right_bracket = extrude_rsolid(bracket, height=1)
        parts.append(right_bracket)
    
    return parts

parts = create_complex_part()
```

### 旋转工作平面

```python
import math
from simplecadapi import SimpleWorkplane, make_circle_rface, extrude_rsolid

# 创建多个旋转的工作平面
def create_rotated_cylinders():
    cylinders = []
    
    for i in range(6):
        angle = i * math.pi / 3  # 每60度一个
        
        # 创建旋转的工作平面
        with SimpleWorkplane(
            origin=(0, 0, 0),
            normal=(math.cos(angle), math.sin(angle), 0),
            x_dir=(0, 0, 1)
        ) as wp:
            circle = make_circle_rface(radius=0.5)
            cylinder = extrude_rsolid(circle, height=3)
            cylinders.append(cylinder)
    
    return cylinders

cylinders = create_rotated_cylinders()
```

### 沿路径创建工作平面

```python
from simplecadapi import SimpleWorkplane, make_box_rsolid

def create_path_features():
    # 定义路径点
    path_points = [
        (0, 0, 0),
        (1, 0, 0),
        (2, 1, 0),
        (3, 1, 1),
        (4, 0, 1)
    ]
    
    features = []
    
    for i, point in enumerate(path_points):
        # 计算朝向下一个点的方向
        if i < len(path_points) - 1:
            next_point = path_points[i + 1]
            direction = (
                next_point[0] - point[0],
                next_point[1] - point[1],
                next_point[2] - point[2]
            )
        else:
            direction = (1, 0, 0)  # 最后一个点使用默认方向
        
        with SimpleWorkplane(origin=point, x_dir=direction) as wp:
            feature = make_box_rsolid(0.2, 0.2, 0.2)
            features.append(feature)
    
    return features

features = create_path_features()
```

## 坐标系转换

SimpleWorkplane 会自动处理坐标系转换：

- 输入的坐标和方向向量在当前坐标系中定义
- 内部会转换为全局坐标系
- 自动处理正交化以确保坐标系的正确性

## 字符串表示

```python
from simplecadapi import SimpleWorkplane

wp = SimpleWorkplane(origin=(1, 2, 3))
print(wp)
```

输出：
```
SimpleWorkplane:
  coordinate_system:
    CoordinateSystem:
      origin: [1.000, 2.000, 3.000]
      x_axis: [1.000, 0.000, 0.000]
      y_axis: [0.000, 1.000, 0.000]
      z_axis: [0.000, 0.000, 1.000]
```

## 与 CADQuery 的兼容性

SimpleWorkplane 可以无缝转换为 CADQuery 的 Workplane：

```python
from simplecadapi import SimpleWorkplane

wp = SimpleWorkplane(origin=(0, 0, 1))
cq_wp = wp.to_cq_workplane()

# 可以在 CADQuery 工作平面上进行操作
cq_result = cq_wp.box(1, 1, 1)
```

## 注意事项

- 使用 `with` 语句时，工作平面会自动管理坐标系栈
- 嵌套工作平面中的坐标都是相对于父工作平面的
- 如果法向量和X轴方向平行，系统会自动选择合适的Y轴方向
- 坐标系会自动正交化以确保正确性
