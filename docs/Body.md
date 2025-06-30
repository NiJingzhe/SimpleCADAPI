# Body 类文档

## 概述
Body类表示三维实体对象，是所有三维建模操作的结果。它封装了CADQuery的实体对象，提供统一的接口进行实体操作。

## 类定义
```python
class Body:
    """三维实体"""
```

## 构造函数
```python
def __init__(self, cq_solid: Any = None)
```

### 参数
- `cq_solid`: CADQuery的Solid或Workplane对象，默认为None

## 属性
- `cq_solid`: CADQuery的实体对象
- `id`: 唯一标识符，自动递增
- `_id_counter`: 类变量，用于生成唯一ID

## 方法

### is_valid() -> bool
检查实体是否有效
- **返回**: 布尔值，True表示实体有效
- 通过检查cq_solid是否为None来判断

### volume() -> float
计算实体体积
- **返回**: 浮点数，实体体积
- **注意**: 当前为简化实现，返回固定值1.0

### to_cq_workplane() -> cq.Workplane
转换为CADQuery工作平面对象
- **返回**: CADQuery Workplane对象
- 如果实体无效则返回空的工作平面

### __repr__() -> str
字符串表示
- **返回**: 包含ID和有效性的字符串

## 使用示例

### 创建基础实体
```python
from simplecadapi.operations import make_box, make_cylinder, make_sphere

# 创建立方体
box = make_box(10, 5, 3)
print(box)  # Body(id=0, valid=True)
print(f"体积: {box.volume()}")
print(f"是否有效: {box.is_valid()}")

# 创建圆柱体
cylinder = make_cylinder(5, 10)
print(cylinder)  # Body(id=1, valid=True)

# 创建球体
sphere = make_sphere(3)
print(sphere)  # Body(id=2, valid=True)
```

### 通过拉伸创建实体
```python
from simplecadapi.operations import make_rectangle, extrude

# 创建矩形草图
rect_sketch = make_rectangle(10, 8)

# 拉伸成立方体
extruded_body = extrude(rect_sketch, distance=5)
print(f"拉伸实体: {extruded_body}")
print(f"有效性: {extruded_body.is_valid()}")
```

### 布尔运算
```python
from simplecadapi.operations import union, cut, intersect

# 创建两个重叠的立方体
box1 = make_box(10, 10, 10)
box2 = make_box(8, 8, 8)  # 较小的立方体

# 布尔并运算
union_result = union(box1, box2)
print(f"并运算结果: {union_result}")

# 布尔减运算
cut_result = cut(box1, box2)
print(f"减运算结果: {cut_result}")

# 布尔交运算
intersect_result = intersect(box1, box2)
print(f"交运算结果: {intersect_result}")
```

### 实体修饰操作
```python
from simplecadapi.operations import fillet, chamfer, shell

# 创建基础立方体
base_box = make_box(20, 20, 10)

# 圆角操作
filleted_box = fillet(base_box, [], 2.0)  # 半径2的圆角
print(f"圆角实体: {filleted_box}")

# 倒角操作
chamfered_box = chamfer(base_box, [], 1.5)  # 距离1.5的倒角
print(f"倒角实体: {chamfered_box}")

# 抽壳操作
shelled_box = shell(base_box, 2.0)  # 壁厚2的抽壳
print(f"抽壳实体: {shelled_box}")
```

### 阵列操作
```python
from simplecadapi.operations import pattern_linear, pattern_2d, pattern_radial
from simplecadapi.core import Point

# 创建基础实体
unit_box = make_box(2, 2, 2)

# 线性阵列
linear_array = pattern_linear(
    unit_box, 
    direction=(1, 0, 0),  # X方向
    count=5, 
    spacing=4
)
print(f"线性阵列: {linear_array}")

# 2D阵列
grid_array = pattern_2d(
    unit_box,
    x_direction=(1, 0, 0),
    y_direction=(0, 1, 0),
    x_count=3,
    y_count=4,
    x_spacing=5,
    y_spacing=3
)
print(f"2D阵列: {grid_array}")

# 径向阵列
center_point = Point((0, 0, 0))
radial_array = pattern_radial(
    unit_box,
    center=center_point,
    axis=(0, 0, 1),
    count=8,
    angle=6.28  # 360度
)
print(f"径向阵列: {radial_array}")
```

### 与CADQuery集成
```python
import cadquery as cq

# 获取CADQuery工作平面
body = make_box(10, 10, 10)
workplane = body.to_cq_workplane()

# 进行CADQuery原生操作
cq_result = workplane.faces(">Z").hole(3)  # 在顶面钻孔

# 创建新的Body对象
modified_body = Body(cq_result)
print(f"修改后的实体: {modified_body}")
```

### 实体验证和错误处理
```python
# 创建空实体
empty_body = Body()
print(f"空实体有效性: {empty_body.is_valid()}")  # False

# 验证实体操作结果
try:
    # 可能失败的操作
    result = union(box1, box2)
    if result.is_valid():
        print("操作成功")
    else:
        print("操作失败，结果无效")
except ValueError as e:
    print(f"操作异常: {e}")
```

### 批量实体管理
```python
# 创建多个实体
bodies = []
for i in range(5):
    box = make_box(2, 2, 2)
    bodies.append(box)

# 检查所有实体的有效性
valid_count = sum(1 for body in bodies if body.is_valid())
print(f"有效实体数量: {valid_count}/{len(bodies)}")

# 输出所有实体信息
for body in bodies:
    print(f"实体 {body.id}: 有效={body.is_valid()}, 体积={body.volume()}")
```

### 实体ID管理
```python
# 查看当前ID计数器
print(f"下一个实体ID: {Body._id_counter}")

# 创建多个实体观察ID分配
body1 = Body()
body2 = Body()
body3 = Body()

print(f"Body1 ID: {body1.id}")  # 自动分配的ID
print(f"Body2 ID: {body2.id}")  # 递增的ID
print(f"Body3 ID: {body3.id}")  # 继续递增
```

## 高级用法

### 自定义体积计算（未来实现）
```python
# 注意：当前体积计算为简化实现
# 未来版本将提供真实的体积计算
def get_real_volume(body):
    """获取真实体积（示例代码）"""
    if not body.is_valid():
        return 0.0
    
    # 未来实现：
    # if hasattr(body.cq_solid, 'solids'):
    #     solids = body.cq_solid.solids()
    #     if solids.size() > 0:
    #         return solids.first().volume()
    return body.volume()
```

## 注意事项
1. Body对象封装CADQuery实体，提供统一接口
2. 每个实体都有唯一的ID，便于追踪和管理
3. 实体的有效性检查很重要，无效实体不能参与操作
4. 当前体积计算为简化实现，返回固定值
5. 支持与CADQuery的双向转换
6. 所有建模操作的最终结果都是Body对象
7. 实体创建失败时会抛出ValueError异常
