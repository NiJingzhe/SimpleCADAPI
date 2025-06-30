# create_workplane_from_face

## 定义
```python
def create_workplane_from_face(body: Body, tag: str)
```

## 作用
从实体的指定标签面创建工作平面。工作平面是CAD设计中的重要概念，用于在特定面上进行二维草图绘制和后续的三维操作。该函数允许在现有几何体的面上建立新的坐标系统。

**参数说明：**
- `body`: 包含面的实体
- `tag`: 要创建工作平面的面标签

**返回值：**
- 返回CADQuery Workplane对象

## 示例代码

### 基础工作平面创建
```python
from simplecadapi.operations import *

# 创建立方体并标记面
cube = make_box(30, 30, 30, center=True)
tag_faces_automatically(cube, "box")

# 从顶面创建工作平面
top_workplane = create_workplane_from_face(cube, "top")
print("已从顶面创建工作平面")

# 从侧面创建工作平面
front_workplane = create_workplane_from_face(cube, "front")
print("已从前面创建工作平面")
```

### 圆柱体工作平面
```python
from simplecadapi.operations import *

# 创建圆柱体
cylinder = make_cylinder(radius=15, height=25)
tag_faces_automatically(cylinder, "cylinder")

# 从圆柱体顶面创建工作平面
cylinder_top_wp = create_workplane_from_face(cylinder, "top")

# 从圆柱体侧面创建工作平面
cylinder_side_wp = create_workplane_from_face(cylinder, "side")

print("已创建圆柱体工作平面")
```

### 在工作平面上绘制草图
```python
from simplecadapi.operations import *

# 创建基础几何体
base_box = make_box(40, 30, 10, center=True)
tag_faces_automatically(base_box, "box")

# 从顶面创建工作平面
workplane = create_workplane_from_face(base_box, "top")

# 在工作平面上绘制圆形（这里简化处理）
# 注意：实际使用时可能需要通过CADQuery接口操作
# circle_on_plane = workplane.circle(5)

print("已在工作平面上绘制草图")
```

### 复杂几何体的工作平面
```python
from simplecadapi.operations import *

# 创建复杂几何体
base_cylinder = make_cylinder(radius=12, height=20)
top_box = make_box(15, 15, 8, center=True)

# 合并几何体
complex_body = union(base_cylinder, top_box)

# 手动标记特定面
complex_body.tag_face(0, "cylinder_bottom")
complex_body.tag_face(1, "cylinder_top")
complex_body.tag_face(2, "box_top")

# 从不同面创建工作平面
cylinder_wp = create_workplane_from_face(complex_body, "cylinder_top")
box_wp = create_workplane_from_face(complex_body, "box_top")

print("已创建复杂几何体的工作平面")
```

### 工作平面验证
```python
from simplecadapi.operations import *

# 创建测试几何体
test_box = make_box(25, 20, 15, center=True)
tag_faces_automatically(test_box, "box")

# 验证标签存在
face_info = get_face_info(test_box)
print(f"可用标签: {list(face_info['tagged_faces'].keys())}")

# 创建工作平面
if "top" in face_info['tagged_faces']:
    workplane = create_workplane_from_face(test_box, "top")
    print("工作平面创建成功")
else:
    print("找不到'top'标签")
```

### 多个工作平面创建
```python
from simplecadapi.operations import *

# 创建六面体
hexahedron = make_box(20, 20, 20, center=True)
tag_faces_automatically(hexahedron, "box")

# 创建所有面的工作平面
workplanes = {}
face_tags = ["top", "bottom", "front", "back", "left", "right"]

for tag in face_tags:
    try:
        wp = create_workplane_from_face(hexahedron, tag)
        workplanes[tag] = wp
        print(f"已创建{tag}面工作平面")
    except Exception as e:
        print(f"创建{tag}面工作平面失败: {e}")

print(f"总共创建了 {len(workplanes)} 个工作平面")
```

### 倾斜面工作平面
```python
from simplecadapi.operations import *

# 创建楔形体（简化处理）
base_rect = make_rectangle(30, 20)
wedge = extrude(base_rect, 15)

# 手动标记倾斜面
wedge.tag_face(0, "sloped_face")
wedge.tag_face(1, "bottom_face")

# 从倾斜面创建工作平面
try:
    sloped_workplane = create_workplane_from_face(wedge, "sloped_face")
    print("已从倾斜面创建工作平面")
except Exception as e:
    print(f"倾斜面工作平面创建失败: {e}")
```

### 工作平面链式操作
```python
from simplecadapi.operations import *

# 创建基础平台
platform = make_box(50, 40, 5, center=True)
tag_faces_automatically(platform, "box")

# 创建第一级工作平面
level1_wp = create_workplane_from_face(platform, "top")

# 在第一级上添加几何体（简化处理）
level1_box = make_box(20, 15, 8, center=True)

# 模拟在工作平面上的构建过程
print("已创建分级工作平面系统")
```

### 工作平面错误处理
```python
from simplecadapi.operations import *

# 创建几何体
error_test = make_cylinder(radius=10, height=20)

# 尝试创建工作平面（未标记面）
try:
    wp = create_workplane_from_face(error_test, "nonexistent")
    print("工作平面创建成功")
except Exception as e:
    print(f"工作平面创建失败: {e}")

# 正确的流程
tag_faces_automatically(error_test, "cylinder")
try:
    wp = create_workplane_from_face(error_test, "top")
    print("正确创建工作平面")
except Exception as e:
    print(f"仍然失败: {e}")
```

### 工作平面用于特征添加
```python
from simplecadapi.operations import *

# 创建主体
main_body = make_box(35, 25, 15, center=True)
tag_faces_automatically(main_body, "box")

# 从侧面创建工作平面，用于添加特征
side_workplane = create_workplane_from_face(main_body, "front")

# 在工作平面上规划特征位置
# 这里演示概念，实际需要更复杂的操作
feature_hole = make_cylinder(radius=3, height=20)

# 模拟在工作平面坐标系中定位特征
print("已在工作平面上规划特征")
```

### 曲面工作平面
```python
from simplecadapi.operations import *

# 创建球体
sphere = make_sphere(radius=15)
tag_faces_automatically(sphere, "sphere")

# 尝试从球面创建工作平面
try:
    sphere_workplane = create_workplane_from_face(sphere, "surface")
    print("球面工作平面创建成功")
except Exception as e:
    print(f"球面工作平面创建失败: {e}")
    print("球面可能需要特殊处理")
```

## 注意事项
1. 目标面必须先用标签标记（使用 `tag_faces_automatically` 或手动标记）
2. 如果指定标签不存在，函数会抛出异常
3. 工作平面的坐标系统基于面的法向量和位置
4. 平面面（如立方体面）最适合创建工作平面
5. 曲面可能需要特殊处理或不支持
6. 返回的工作平面可用于后续的CADQuery操作
7. 建议在创建工作平面前验证标签存在性
8. 工作平面是后续草图绘制和特征添加的基础
