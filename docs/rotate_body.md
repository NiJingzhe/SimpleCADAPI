# rotate_body

## 描述
围绕指定轴旋转实体，创建新的实体对象。

## 语法
```python
rotate_body(body: Body, angle: float, axis: Tuple[float, float, float]) -> Body
```

## 参数
- **body** (Body): 要旋转的实体
- **angle** (float): 旋转角度（弧度）
- **axis** (Tuple[float, float, float]): 旋转轴方向向量 (x, y, z)

## 返回值
- **Body**: 旋转后的新实体

## 异常
- **ValueError**: 当输入实体无效时抛出

## 示例

### 基本旋转操作
```python
import math
from simplecadapi import *

# 创建一个立方体
cube = make_box(2.0, 1.0, 1.0)

# 绕Z轴旋转45度
rotated_cube = rotate_body(cube, angle=math.pi/4, axis=(0, 0, 1))

# 绕X轴旋转90度
x_rotated = rotate_body(cube, angle=math.pi/2, axis=(1, 0, 0))
```

### 复杂旋转
```python
# 创建一个圆柱体
cylinder = make_cylinder(0.5, 3.0)

# 绕Y轴旋转，使圆柱体水平放置
horizontal_cylinder = rotate_body(cylinder, angle=math.pi/2, axis=(0, 1, 0))

# 绕任意轴旋转
arbitrary_axis = (1, 1, 1)  # 对角线方向
diagonal_rotated = rotate_body(cylinder, angle=math.pi/3, axis=arbitrary_axis)
```

### 多次旋转
```python
# 创建基础形状
base_shape = make_box(2.0, 0.5, 0.5)

# 连续旋转
step1 = rotate_body(base_shape, angle=math.pi/4, axis=(1, 0, 0))
step2 = rotate_body(step1, angle=math.pi/6, axis=(0, 1, 0))
final = rotate_body(step2, angle=math.pi/8, axis=(0, 0, 1))

export_stl(final, "multi_rotated.stl")
```

### 创建旋转阵列
```python
# 创建基础齿形
tooth = make_box(0.2, 1.0, 0.5)
tooth = translate_body(tooth, vector=(1.0, 0.0, 0.0))  # 移到半径位置

# 创建齿轮的齿
teeth = [tooth]
tooth_count = 8
for i in range(1, tooth_count):
    angle = 2 * math.pi * i / tooth_count
    rotated_tooth = rotate_body(tooth, angle=angle, axis=(0, 0, 1))
    teeth.append(rotated_tooth)

# 合并所有齿
gear_teeth = teeth[0]
for t in teeth[1:]:
    gear_teeth = union(gear_teeth, t)
```

## 角度转换
```python
import math

# 度数转弧度
degrees_to_radians = lambda deg: deg * math.pi / 180

# 常用角度
angle_30_deg = degrees_to_radians(30)   # 30度
angle_45_deg = math.pi / 4              # 45度
angle_90_deg = math.pi / 2              # 90度
angle_180_deg = math.pi                 # 180度

# 使用度数转换
rotated = rotate_body(cube, angle=degrees_to_radians(45), axis=(0, 0, 1))
```

## 注意事项
- 旋转操作不会修改原始实体，而是创建新的实体
- 角度使用弧度制，正值为逆时针旋转（右手定则）
- 旋转轴向量会被自动标准化
- 旋转中心固定在原点 (0, 0, 0)
- 轴向量使用SimpleCAD坐标系 (x, y, z)

## 相关函数
- [translate_body](translate_body.md) - 平移实体
- [make_radial_pattern](make_radial_pattern.md) - 径向阵列（包含旋转）
- [revolve](revolve.md) - 旋转草图生成实体
