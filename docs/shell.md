# shell 函数文档

## 定义
```python
def shell(body: Body, thickness: float, face_tags: Optional[List[str]] = None) -> Body
```

## 作用
对3D实体进行抽壳操作，创建指定壁厚的空心结构。可以选择性地移除某些面形成开口。

## 参数
- `body` (Body): 要抽壳的实体
- `thickness` (float): 壁厚
- `face_tags` (Optional[List[str]]): 要移除的面标签列表，这些面在抽壳后会被去掉形成开口

## 返回值
- `Body`: 抽壳后的实体

## 示例代码

### 基础抽壳操作（来自comprehensive_test）
```python
from simplecadapi import *

# 创建测试立方体
test_cube = make_box(2.0, 2.0, 2.0, center=True)

# 抽壳操作，移除顶面和前面形成开口
hollow_box = shell(test_cube, thickness=0.1, face_tags=["top", "front"])
```

### 完全封闭的抽壳
```python
from simplecadapi import *

# 创建球体并进行完全抽壳
sphere = make_sphere(1.5)
hollow_sphere = shell(sphere, thickness=0.1)  # 无开口的空心球
```

### 圆柱体抽壳
```python
from simplecadapi import *

# 创建圆柱体
cylinder = make_cylinder(1.0, 2.0)

# 移除顶面形成开口圆柱（如杯子）
cup = shell(cylinder, thickness=0.08, face_tags=["top"])
```

### 复杂形状抽壳
```python
from simplecadapi import *

# 创建复杂的拉伸体
complex_profile = make_rectangle(3.0, 2.0, center=True)
complex_solid = extrude(complex_profile, distance=1.5)

# 抽壳形成薄壁容器
thin_wall_container = shell(complex_solid, thickness=0.05, face_tags=["top"])
```

### 瓶子形状抽壳
```python
from simplecadapi import *

# 使用放样创建瓶子形状
bottom = make_circle(1.0)

with LocalCoordinateSystem(origin=(0, 0, 1.5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    middle = make_circle(1.2)

with LocalCoordinateSystem(origin=(0, 0, 3.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    neck = make_circle(0.4)

bottle_solid = loft([bottom, middle, neck])

# 抽壳形成空心瓶子，移除顶部形成瓶口
hollow_bottle = shell(bottle_solid, thickness=0.1, face_tags=["top"])
```

### 多开口抽壳
```python
from simplecadapi import *

# 创建立方体
cube = make_box(3.0, 3.0, 3.0, center=True)

# 移除多个面形成多个开口
multi_opening_box = shell(
    cube, 
    thickness=0.15, 
    face_tags=["top", "front", "right"]
)
```

### 薄壁电子外壳
```python
from simplecadapi import *

# 创建电子设备外壳基本形状
case_profile = make_rectangle(8.0, 6.0, center=True)
case_solid = extrude(case_profile, distance=2.0)

# 移除顶面形成可打开的外壳
case_bottom = shell(case_solid, thickness=0.2, face_tags=["top"])

# 创建配套的顶盖（稍微小一点以便配合）
with LocalCoordinateSystem(origin=(0, 0, 2.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    lid_profile = make_rectangle(7.6, 5.6, center=True)  # 略小
    case_lid = extrude(lid_profile, distance=0.3)
```

### 渐变壁厚效果
```python
from simplecadapi import *

# 创建基础圆柱
base_cylinder = make_cylinder(2.0, 3.0)

# 先进行基础抽壳
thin_cylinder = shell(base_cylinder, thickness=0.1, face_tags=["top"])

# 在底部添加加厚结构
with LocalCoordinateSystem(origin=(0, 0, 0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    thick_bottom = make_cylinder(1.9, 0.3)  # 厚底
    reinforced_base = union(thin_cylinder, thick_bottom)
```

### 带孔洞的抽壳
```python
from simplecadapi import *

# 创建立方体
main_body = make_box(4.0, 4.0, 4.0, center=True)

# 先添加孔洞
hole_cylinder = make_cylinder(0.5, 5.0)  # 穿透孔
body_with_hole = cut(main_body, hole_cylinder)

# 再进行抽壳
hollow_body_with_hole = shell(body_with_hole, thickness=0.2, face_tags=["top"])
```

### 复杂容器设计
```python
from simplecadapi import *

# 创建有把手的容器基本形状
# 主体
main_body = make_cylinder(1.5, 2.5)

# 把手（简化为小圆柱）
with LocalCoordinateSystem(origin=(2.0, 0, 1.25), x_axis=(0, 1, 0), y_axis=(0, 0, 1)):
    handle = make_cylinder(0.2, 1.0)

# 合并主体和把手
mug_solid = union(main_body, handle)

# 抽壳形成杯子
mug = shell(mug_solid, thickness=0.08, face_tags=["top"])
```

### 分层抽壳效果
```python
from simplecadapi import *

# 创建分层结构
layer1 = make_box(5.0, 5.0, 1.0, center=True)

with LocalCoordinateSystem(origin=(0, 0, 1.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    layer2 = make_box(4.0, 4.0, 1.0, center=True)

with LocalCoordinateSystem(origin=(0, 0, 2.0), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    layer3 = make_box(3.0, 3.0, 1.0, center=True)

stepped_solid = union(layer1, layer2)
stepped_solid = union(stepped_solid, layer3)

# 抽壳形成阶梯式薄壁结构
stepped_shell = shell(stepped_solid, thickness=0.1, face_tags=["top"])
```

### 检查抽壳质量
```python
from simplecadapi import *

# 创建测试对象
test_object = make_cylinder(2.0, 3.0)

# 进行抽壳
shelled_object = shell(test_object, thickness=0.2)

# 验证抽壳是否成功
if shelled_object.is_valid():
    print("抽壳操作成功")
    # 可以进行进一步的操作
else:
    print("抽壳操作失败，检查参数")
```

## 注意事项
- thickness必须为正值，且不能太大以致于内部空间消失
- face_tags列表中的标签必须存在于实体上
- 如果不指定face_tags，将创建完全封闭的空心结构
- 抽壳操作可能在尖锐边缘或复杂几何处失败
- 壁厚过薄可能导致制造困难或结构不稳定
- 适用于创建容器、外壳、薄壁结构等
- 抽壳后的实体可以进行进一步的布尔运算、圆角等操作
