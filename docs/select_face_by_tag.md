# select_face_by_tag

## 定义
```python
def select_face_by_tag(body: Body, tags: List[str])
```

## 作用
根据标签选择实体的面。该函数允许通过预先设置的标签来选择实体的特定面，用于后续的操作如倒角、圆角、工作平面创建等。这是面向对象CAD操作的重要功能。

**参数说明：**
- `body`: 要选择面的实体
- `tags`: 要选择的面标签列表

**返回值：**
- 返回选中的面对象列表（CADQuery Face对象）

## 示例代码

### 基础面选择
```python
from simplecadapi.operations import *

# 创建立方体并自动标记面
cube = make_box(20, 20, 20, center=True)
tag_faces_automatically(cube, "box")

# 选择顶面
top_faces = select_face_by_tag(cube, ["top"])
print(f"选择了 {len(top_faces)} 个顶面")

# 选择侧面
side_faces = select_face_by_tag(cube, ["front", "back"])
print(f"选择了 {len(side_faces)} 个侧面")
```

### 圆柱体面选择
```python
from simplecadapi.operations import *

# 创建圆柱体并标记面
cylinder = make_cylinder(radius=10, height=25)
tag_faces_automatically(cylinder, "cylinder")

# 选择顶面和底面
caps = select_face_by_tag(cylinder, ["top", "bottom"])
print(f"选择了 {len(caps)} 个端面")

# 选择侧面
side = select_face_by_tag(cylinder, ["side"])
print(f"选择了 {len(side)} 个侧面")
```

### 复杂几何体面选择
```python
from simplecadapi.operations import *

# 创建复杂几何体
base_box = make_box(30, 20, 10, center=True)
top_cylinder = make_cylinder(radius=8, height=8)

# 合并几何体
complex_body = union(base_box, top_cylinder)

# 手动标记特定面
# 假设我们知道面的索引
complex_body.tag_face(0, "base_bottom")
complex_body.tag_face(1, "base_top")
complex_body.tag_face(2, "cylinder_top")

# 选择标记的面
base_faces = select_face_by_tag(complex_body, ["base_bottom", "base_top"])
cylinder_face = select_face_by_tag(complex_body, ["cylinder_top"])

print(f"选择了 {len(base_faces)} 个基础面")
print(f"选择了 {len(cylinder_face)} 个圆柱面")
```

### 用于倒角操作的面选择
```python
from simplecadapi.operations import *

# 创建立方体
cube = make_box(25, 25, 25, center=True)
tag_faces_automatically(cube, "box")

# 选择要倒角的面
faces_to_chamfer = select_face_by_tag(cube, ["top", "front"])

# 注意：实际倒角需要边，这里仅演示面选择
print(f"选择了 {len(faces_to_chamfer)} 个面用于倒角")

# 获取面的信息
for i, face in enumerate(faces_to_chamfer):
    try:
        center = face.Center()
        area = face.Area()
        print(f"面 {i}: 中心点({center.x:.2f}, {center.y:.2f}, {center.z:.2f}), 面积{area:.2f}")
    except:
        print(f"面 {i}: 无法获取信息")
```

### 多标签批量选择
```python
from simplecadapi.operations import *

# 创建球体
sphere = make_sphere(radius=12)
tag_faces_automatically(sphere, "sphere")

# 创建立方体
cube = make_box(15, 15, 15, center=True)
tag_faces_automatically(cube, "box")

# 组合模型
combined = union(sphere, cube)

# 选择多个不同类型的面
various_faces = select_face_by_tag(combined, ["top", "bottom", "front"])
print(f"选择了 {len(various_faces)} 个不同类型的面")
```

### 自定义标签系统
```python
from simplecadapi.operations import *

# 创建自定义形状
custom_box = make_box(40, 30, 20, center=True)

# 手动创建自定义标签系统
custom_box.tag_face(0, "mounting_surface")
custom_box.tag_face(1, "display_surface")
custom_box.tag_face(2, "connection_port")
custom_box.tag_face(3, "ventilation_side")

# 根据功能选择面
mounting_faces = select_face_by_tag(custom_box, ["mounting_surface"])
display_faces = select_face_by_tag(custom_box, ["display_surface"])
functional_faces = select_face_by_tag(custom_box, ["connection_port", "ventilation_side"])

print(f"安装面: {len(mounting_faces)} 个")
print(f"显示面: {len(display_faces)} 个")
print(f"功能面: {len(functional_faces)} 个")
```

### 面选择验证
```python
from simplecadapi.operations import *

# 创建测试几何体
test_cylinder = make_cylinder(radius=8, height=20)
tag_faces_automatically(test_cylinder, "cylinder")

# 尝试选择存在的标签
existing_faces = select_face_by_tag(test_cylinder, ["top", "side"])
print(f"成功选择 {len(existing_faces)} 个面")

# 尝试选择不存在的标签
try:
    missing_faces = select_face_by_tag(test_cylinder, ["nonexistent"])
    print(f"选择了 {len(missing_faces)} 个面（可能为空）")
except Exception as e:
    print(f"选择失败: {e}")

# 混合存在和不存在的标签
mixed_faces = select_face_by_tag(test_cylinder, ["top", "nonexistent", "side"])
print(f"混合选择结果: {len(mixed_faces)} 个面")
```

### 工作平面准备
```python
from simplecadapi.operations import *

# 创建工作基础
work_base = make_box(50, 40, 15, center=True)
tag_faces_automatically(work_base, "box")

# 选择用于创建工作平面的面
workplane_faces = select_face_by_tag(work_base, ["top"])

if workplane_faces:
    print("已选择面，可以创建工作平面")
    # 这里可以继续使用 create_workplane_from_face
else:
    print("未找到合适的面")
```

### 面选择状态检查
```python
from simplecadapi.operations import *

# 创建几何体
check_box = make_box(20, 20, 20, center=True)

# 检查标签状态
face_info = get_face_info(check_box)
print(f"总面数: {face_info['total_faces']}")
print(f"已标记面: {face_info['tagged_faces']}")

# 先标记再选择
tag_faces_automatically(check_box, "box")

# 重新检查
face_info = get_face_info(check_box)
print(f"标记后的面信息: {face_info['tagged_faces']}")

# 现在可以成功选择
all_tagged_faces = select_face_by_tag(check_box, ["top", "bottom", "front", "back", "left", "right"])
print(f"选择了所有标记面: {len(all_tagged_faces)} 个")
```

### 条件选择
```python
from simplecadapi.operations import *

# 创建多个几何体
geometries = {
    "small_box": make_box(10, 10, 10, center=True),
    "large_box": make_box(25, 25, 25, center=True),
    "cylinder": make_cylinder(radius=8, height=15)
}

# 为每个几何体标记面
for name, geo in geometries.items():
    if "box" in name:
        tag_faces_automatically(geo, "box")
    else:
        tag_faces_automatically(geo, "cylinder")

# 有条件地选择面
for name, geo in geometries.items():
    if "box" in name:
        faces = select_face_by_tag(geo, ["top", "bottom"])
        print(f"{name}: 选择了 {len(faces)} 个水平面")
    else:
        faces = select_face_by_tag(geo, ["top", "bottom", "side"])
        print(f"{name}: 选择了 {len(faces)} 个面")
```

## 注意事项
1. 面必须先用 `tag_faces_automatically()` 或手动标记才能选择
2. 如果标签不存在，返回空列表而不报错
3. 可以同时选择多个标签对应的面
4. 返回的是CADQuery Face对象列表，可用于后续操作
5. 面的选择是基于实体创建时的拓扑结构
6. 复杂几何体可能需要自定义标签系统
7. 建议在面选择前检查标签是否存在
8. 选择结果可能包含重复的面（如果面有多个标签）
