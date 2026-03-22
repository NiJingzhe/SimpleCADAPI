# CoordinateSystem

## Overview

`CoordinateSystem` is the 3D coordinate system class in SimpleCAD API, used for defining and managing coordinate systems in 3D space. SimpleCAD uses a Z-up right-handed coordinate system with origin at (0, 0, 0), X-axis forward, Y-axis right, and Z-axis up.

## Class Definition

```python
class CoordinateSystem:
    """三维坐标系
    
    SimpleCAD使用Z向上的右手坐标系，原点在(0, 0, 0)，X轴向前，Y轴向右，Z轴向上
    """
```

## Usage

- Define local coordinate systems
- Coordinate transformation (local to global coordinates)
- Conversion with CADQuery coordinate systems
- Foundation for geometric transformations

## Constructor

### `__init__(origin, x_axis, y_axis)`

Initialize a coordinate system.

**Parameters:**
- `origin` (Tuple[float, float, float], optional): Coordinate system origin, default (0, 0, 0)
- `x_axis` (Tuple[float, float, float], optional): X-axis direction vector, default (1, 0, 0)
- `y_axis` (Tuple[float, float, float], optional): Y-axis direction vector, default (0, 1, 0)

**Exceptions:**
- `ValueError`: Raised when input coordinates or direction vectors are invalid

**Example:**
```python
from simplecadapi import CoordinateSystem

# 默认坐标系（世界坐标系）
world_cs = CoordinateSystem()

# 自定义坐标系
custom_cs = CoordinateSystem(
    origin=(1, 2, 3),
    x_axis=(1, 0, 0),
    y_axis=(0, 1, 0)
)

# 旋转的坐标系
rotated_cs = CoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(0.707, 0.707, 0),  # 绕Z轴旋转45度
    y_axis=(-0.707, 0.707, 0)
)
```

## Main Properties

- `origin`: Coordinate system origin (numpy.ndarray)
- `x_axis`: X-axis direction vector (numpy.ndarray)
- `y_axis`: Y-axis direction vector (numpy.ndarray)
- `z_axis`: Z-axis direction vector (numpy.ndarray, automatically calculated)

## Common Methods

### `transform_point(point)`

Transform local coordinates to global coordinates.

**Parameters:**
- `point` (numpy.ndarray): Local coordinate point

**Returns:**
- `numpy.ndarray`: Global coordinate point

**Example:**
```python
import numpy as np
from simplecadapi import CoordinateSystem

cs = CoordinateSystem(origin=(1, 0, 0))
local_point = np.array([1, 0, 0])
global_point = cs.transform_point(local_point)
print(global_point)  # [2. 0. 0.]
```

### `transform_vector(vector)`

Transform local direction vectors to global direction vectors (excluding translation).

**Parameters:**
- `vector` (numpy.ndarray): Local direction vector

**Returns:**
- `numpy.ndarray`: Global direction vector

**Example:**
```python
import numpy as np
from simplecadapi import CoordinateSystem

cs = CoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(0, 1, 0),  # X轴指向Y方向
    y_axis=(1, 0, 0)   # Y轴指向X方向
)

local_vector = np.array([1, 0, 0])  # 局部X方向
global_vector = cs.transform_vector(local_vector)
print(global_vector)  # [0. 1. 0.] (全局Y方向)
```

### `to_cq_plane()`

Convert to CADQuery's Plane object.

**Returns:**
- `cadquery.Plane`: CADQuery plane object

**Example:**
```python
from simplecadapi import CoordinateSystem

cs = CoordinateSystem(origin=(0, 0, 1))
cq_plane = cs.to_cq_plane()
```

## Coordinate System Transformation

SimpleCAD uses Z-up coordinate system, while CADQuery uses Y-up coordinate system. The conversion rules are:

- SimpleCAD's X-axis (forward) → CADQuery's Z-axis (forward)
- SimpleCAD's Y-axis (right) → CADQuery's X-axis (right)
- SimpleCAD's Z-axis (up) → CADQuery's Y-axis (up)

## Global Coordinate System

SimpleCAD provides a global world coordinate system:

```python
from simplecadapi import WORLD_CS

print(WORLD_CS.origin)  # [0. 0. 0.]
print(WORLD_CS.x_axis)  # [1. 0. 0.]
print(WORLD_CS.y_axis)  # [0. 1. 0.]
print(WORLD_CS.z_axis)  # [0. 0. 1.]
```

## String Representation

```python
from simplecadapi import CoordinateSystem

cs = CoordinateSystem(origin=(1, 2, 3))
print(cs)
```

Output:
```
CoordinateSystem:
  origin: [1.000, 2.000, 3.000]
  x_axis: [1.000, 0.000, 0.000]
  y_axis: [0.000, 1.000, 0.000]
  z_axis: [0.000, 0.000, 1.000]
```

## Notes

- Input direction vectors are automatically normalized
- Z-axis is automatically calculated via the cross product of X-axis and Y-axis
- If a zero vector is input, a ValueError will be raised
- Coordinate systems should maintain right-handed characteristics
