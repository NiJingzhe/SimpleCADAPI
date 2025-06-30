# tag_faces_automatically

## 定义
```python
def tag_faces_automatically(body: Body, geometry_type: str = "auto")
```

## 作用
自动为实体的面添加标签。该函数根据几何体类型智能识别并标记各个面，为后续的面选择、工作平面创建等操作提供便利。支持自动检测几何体类型或手动指定类型。

**参数说明：**
- `body`: 要添加标签的实体
- `geometry_type`: 几何体类型，可选值包括：
  - `"auto"`: 自动检测（默认）
  - `"box"`: 立方体/长方体
  - `"cylinder"`: 圆柱体
  - `"sphere"`: 球体

**返回值：**
- 无返回值，直接修改实体的面标签

## 示例代码

### 自动检测标记
```python
from simplecadapi.operations import *

# 创建立方体（6个面）
cube = make_box(20, 20, 20, center=True)
tag_faces_automatically(cube, "auto")  # 自动检测为box类型

# 检查标记结果
face_info = get_face_info(cube)
print(f"立方体面标签: {face_info['tagged_faces']}")
export_stl(cube, "output/tagged_cube.stl")
```

### 立方体标记
```python
from simplecadapi.operations import *

# 创建长方体
box = make_box(30, 20, 15, center=True)
tag_faces_automatically(box, "box")

# 查看标记的面
face_info = get_face_info(box)
print("长方体面标签:")
for tag, count in face_info['tagged_faces'].items():
    print(f"  {tag}: {count} 个面")

# 标准立方体标签通常包括：top, bottom, front, back, left, right
```

### 圆柱体标记
```python
from simplecadapi.operations import *

# 创建圆柱体（3个面：顶面、底面、侧面）
cylinder = make_cylinder(radius=12, height=25)
tag_faces_automatically(cylinder, "cylinder")

# 检查圆柱体标签
face_info = get_face_info(cylinder)
print("圆柱体面标签:")
for tag, count in face_info['tagged_faces'].items():
    print(f"  {tag}: {count} 个面")

# 圆柱体标签通常包括：top, bottom, side
export_stl(cylinder, "output/tagged_cylinder.stl")
```

### 球体标记
```python
from simplecadapi.operations import *

# 创建球体（1个面）
sphere = make_sphere(radius=15)
tag_faces_automatically(sphere, "sphere")

# 检查球体标签
face_info = get_face_info(sphere)
print("球体面标签:")
for tag, count in face_info['tagged_faces'].items():
    print(f"  {tag}: {count} 个面")

# 球体标签通常只有：surface
export_stl(sphere, "output/tagged_sphere.stl")
```

### 复杂几何体自动检测
```python
from simplecadapi.operations import *

# 创建不同类型的几何体进行测试
geometries = [
    ("cube", make_box(15, 15, 15, center=True)),
    ("rect_box", make_box(25, 15, 10, center=True)),
    ("cylinder", make_cylinder(radius=8, height=20)),
    ("sphere", make_sphere(radius=12))
]

for name, geo in geometries:
    # 使用自动检测
    tag_faces_automatically(geo, "auto")
    
    # 查看检测结果
    face_info = get_face_info(geo)
    print(f"{name} 自动检测结果:")
    print(f"  总面数: {face_info['total_faces']}")
    print(f"  标签: {list(face_info['tagged_faces'].keys())}")
    print()
```

### 复杂组合几何体标记
```python
from simplecadapi.operations import *

# 创建复杂几何体
base_box = make_box(40, 30, 10, center=True)
top_cylinder = make_cylinder(radius=10, height=15)

# 组合几何体
complex_shape = union(base_box, top_cylinder)

# 对复杂几何体使用自动标记
tag_faces_automatically(complex_shape, "auto")

# 查看复杂几何体的标记结果
face_info = get_face_info(complex_shape)
print("复杂几何体标记结果:")
print(f"总面数: {face_info['total_faces']}")
print(f"标记面数: {sum(face_info['tagged_faces'].values())}")

# 复杂几何体可能使用通用标记：face_0, face_1, etc.
for tag in face_info['tagged_faces']:
    print(f"标签: {tag}")

export_stl(complex_shape, "output/complex_tagged.stl")
```

### 标记后的面选择操作
```python
from simplecadapi.operations import *

# 创建并标记立方体
work_cube = make_box(25, 25, 25, center=True)
tag_faces_automatically(work_cube, "box")

# 现在可以选择特定面
top_faces = select_face_by_tag(work_cube, ["top"])
side_faces = select_face_by_tag(work_cube, ["front", "back", "left", "right"])

print(f"选择的顶面: {len(top_faces)} 个")
print(f"选择的侧面: {len(side_faces)} 个")

# 创建工作平面
if top_faces:
    top_workplane = create_workplane_from_face(work_cube, "top")
    print("已创建顶面工作平面")
```

### 不同类型几何体批处理
```python
from simplecadapi.operations import *

# 创建几何体集合
shapes = {
    "small_box": make_box(10, 10, 10, center=True),
    "large_box": make_box(30, 20, 15, center=True),
    "thin_cylinder": make_cylinder(radius=5, height=30),
    "wide_cylinder": make_cylinder(radius=15, height=8),
    "small_sphere": make_sphere(radius=8),
    "large_sphere": make_sphere(radius=20)
}

# 批量自动标记
for name, shape in shapes.items():
    print(f"标记 {name}...")
    tag_faces_automatically(shape, "auto")
    
    # 验证标记结果
    face_info = get_face_info(shape)
    print(f"  {name}: {face_info['total_faces']} 个面, "
          f"{len(face_info['tagged_faces'])} 个标签")
    
    # 导出标记后的模型
    export_stl(shape, f"output/tagged_{name}.stl")
```

### 标记验证和错误处理
```python
from simplecadapi.operations import *

# 创建测试几何体
test_cylinder = make_cylinder(radius=10, height=20)

# 标记前检查
face_info_before = get_face_info(test_cylinder)
print("标记前:")
print(f"  总面数: {face_info_before['total_faces']}")
print(f"  已标记面: {len(face_info_before['tagged_faces'])}")

# 执行自动标记
try:
    tag_faces_automatically(test_cylinder, "cylinder")
    print("标记成功")
except Exception as e:
    print(f"标记失败: {e}")

# 标记后检查
face_info_after = get_face_info(test_cylinder)
print("标记后:")
print(f"  总面数: {face_info_after['total_faces']}")
print(f"  标记面数: {sum(face_info_after['tagged_faces'].values())}")
print(f"  标签列表: {list(face_info_after['tagged_faces'].keys())}")
```

### 手动指定类型标记
```python
from simplecadapi.operations import *

# 创建可能被误识别的几何体
ambiguous_shape = make_box(20, 20, 20, center=True)  # 正立方体

# 强制指定为box类型
tag_faces_automatically(ambiguous_shape, "box")

# 查看指定类型的标记结果
face_info = get_face_info(ambiguous_shape)
print("强制box类型标记:")
print(f"标签: {list(face_info['tagged_faces'].keys())}")

# 对比自动检测
auto_shape = make_box(20, 20, 20, center=True)
tag_faces_automatically(auto_shape, "auto")
auto_face_info = get_face_info(auto_shape)
print("自动检测标记:")
print(f"标签: {list(auto_face_info['tagged_faces'].keys())}")
```

### 标记状态管理
```python
from simplecadapi.operations import *

# 创建几何体
managed_box = make_box(30, 25, 20, center=True)

# 检查初始状态
print("初始状态:")
initial_info = get_face_info(managed_box)
print(f"未标记面: {initial_info['total_faces'] - sum(initial_info['tagged_faces'].values())}")

# 第一次标记
tag_faces_automatically(managed_box, "box")
print("第一次标记后:")
first_info = get_face_info(managed_box)
print(f"标记面: {sum(first_info['tagged_faces'].values())}")

# 重新标记（会覆盖之前的标记）
tag_faces_automatically(managed_box, "auto")
print("重新标记后:")
second_info = get_face_info(managed_box)
print(f"最终标记面: {sum(second_info['tagged_faces'].values())}")
```

## 注意事项
1. 自动检测基于面的数量：6个面→box，3个面→cylinder，1个面→sphere
2. 复杂几何体（面数不匹配标准类型）会使用通用标记 `face_0`, `face_1` 等
3. 函数会覆盖已有的面标签
4. 标记操作直接修改实体对象，无返回值
5. 不同几何体类型的标签名称是预定义的：
   - Box: top, bottom, front, back, left, right
   - Cylinder: top, bottom, side
   - Sphere: surface
6. 建议在进行面选择或工作平面创建前调用此函数
7. 对于非标准几何体，可能需要手动标记特定面
8. 标记的准确性取决于几何体的规整程度
