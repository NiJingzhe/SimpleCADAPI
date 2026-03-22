# SimpleWorkplane

## Overview

`SimpleWorkplane` is the workplane class in SimpleCAD API, used for defining local coordinate systems and workplanes for geometric modeling. It supports nested usage and can be used as a context manager, providing a local coordinate system environment for geometric operations.

## Class Definition

```python
class SimpleWorkplane:
    """工作平面上下文管理器
    
    用于定义局部坐标系，支持嵌套使用
    """
```

## Usage

- Define local workplanes
- Provide context manager functionality, using with statements to automatically manage coordinate systems
- Support nested coordinate systems
- Conversion with CADQuery Workplane
- Simplify complex geometric modeling

## Constructor

### `__init__(origin, normal, x_dir)`

Initialize a workplane.

**Parameters:**
- `origin` (Tuple[float, float, float], optional): Workplane origin, default (0, 0, 0)
- `normal` (Tuple[float, float, float], optional): Workplane normal vector, default (0, 0, 1)
- `x_dir` (Tuple[float, float, float], optional): Workplane X-axis direction, default (1, 0, 0)

**Example:**
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

## Main Properties

- `cs`: Corresponding coordinate system of the workplane (CoordinateSystem)
- `cq_workplane`: CADQuery workplane object (lazy loaded)

## Common Methods

### Context Manager Methods

SimpleWorkplane supports `with` statements to automatically manage the current coordinate system within the context.

**Example:**
```python
from simplecadapi import SimpleWorkplane, make_box_rsolid

# 在全局坐标系中创建盒子
box1 = make_box_rsolid(1, 1, 1)

# 在局部坐标系中创建盒子
with SimpleWorkplane(origin=(2, 0, 0)) as wp:
    box2 = make_box_rsolid(1, 1, 1)  # 实际位置在 (2, 0, 0)
```


### `to_cq_workplane()`

Convert to CADQuery's Workplane object.

**Returns:**
- `cadquery.Workplane`: CADQuery workplane object

**Example:**
```python
from simplecadapi import SimpleWorkplane

wp = SimpleWorkplane(origin=(0, 0, 1))
cq_wp = wp.to_cq_workplane()
```
## Usage Examples

### Basic Usage

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

### Nested Workplanes

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

### Creating Complex Geometry

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

### Rotated Workplanes

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

### Creating Workplanes Along a Path

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

## Coordinate System Transformation

SimpleWorkplane automatically handles coordinate system transformations:

- Input coordinates and direction vectors are defined in the current coordinate system
- Internally converted to global coordinate system
- Automatically handles orthogonalization to ensure coordinate system correctness

## String Representation

```python
from simplecadapi import SimpleWorkplane

wp = SimpleWorkplane(origin=(1, 2, 3))
print(wp)
```

Output:
```
SimpleWorkplane:
  coordinate_system:
    CoordinateSystem:
      origin: [1.000, 2.000, 3.000]
      x_axis: [1.000, 0.000, 0.000]
      y_axis: [0.000, 1.000, 0.000]
      z_axis: [0.000, 0.000, 1.000]
```

## CADQuery Compatibility

SimpleWorkplane can be seamlessly converted to CADQuery's Workplane:

```python
from simplecadapi import SimpleWorkplane

wp = SimpleWorkplane(origin=(0, 0, 1))
cq_wp = wp.to_cq_workplane()

# 可以在 CADQuery 工作平面上进行操作
cq_result = cq_wp.box(1, 1, 1)
```

## Notes

- When using `with` statements, the workplane automatically manages the coordinate system stack
- Coordinates in nested workplanes are relative to the parent workplane
- If the normal vector and X-axis direction are parallel, the system automatically selects an appropriate Y-axis direction
- Coordinate systems are automatically orthogonalized to ensure correctness
