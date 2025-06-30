# 布尔运算操作函数文档

## 概述
布尔运算是3D建模中的核心操作，允许通过组合、相减和相交操作来创建复杂的几何体。

---

## cut

### 函数签名
```python
def cut(target: Body, tool: Body) -> Body
```

### 参数
- `target`: Body - 被减去的目标实体
- `tool`: Body - 用于减去的工具实体

### 返回值
- `Body` - 布尔减运算后的实体

### 用途
从目标实体中减去工具实体，常用于创建孔洞、槽等特征。

### 示例
```python
from simplecadapi.operations import make_box, make_cylinder, cut

# 在立方体中钻孔
box = make_box(20, 20, 10)
hole = make_cylinder(3, 10)  # 创建与立方体等高的圆柱

# 从立方体中减去圆柱，形成孔
box_with_hole = cut(box, hole)

# 创建复杂的切割
outer_box = make_box(30, 20, 15)
inner_box = make_box(20, 10, 10)
hollow_shape = cut(outer_box, inner_box)

# 创建槽特征
base_part = make_box(50, 20, 10)
slot_cutter = make_box(30, 5, 5)
slotted_part = cut(base_part, slot_cutter)
```

---

## union

### 函数签名
```python
def union(body1: Body, body2: Body) -> Body
```

### 参数
- `body1`: Body - 第一个实体
- `body2`: Body - 第二个实体

### 返回值
- `Body` - 布尔并运算后的实体

### 用途
将两个或多个实体合并成一个连续的实体，常用于组装复杂形状。

### 示例
```python
from simplecadapi.operations import make_box, make_cylinder, union

# 创建T形结构
horizontal_bar = make_box(20, 4, 4)
vertical_bar = make_box(4, 4, 15)
t_shape = union(horizontal_bar, vertical_bar)

# 创建复合几何体
base_cylinder = make_cylinder(8, 5)
top_box = make_box(10, 10, 3)
compound_shape = union(base_cylinder, top_box)

# 多个实体的逐步合并
def union_multiple(bodies):
    """合并多个实体"""
    if len(bodies) < 2:
        return bodies[0] if bodies else None
    
    result = bodies[0]
    for body in bodies[1:]:
        result = union(result, body)
    return result

# 创建多个小立方体并合并
small_boxes = [
    make_box(3, 3, 3),  # 原点处的立方体
    make_box(3, 3, 3),  # 需要在不同位置创建
    make_box(3, 3, 3),
    make_box(3, 3, 3)
]
combined = union_multiple(small_boxes)
```

---

## intersect

### 函数签名
```python
def intersect(body1: Body, body2: Body) -> Body
```

### 参数
- `body1`: Body - 第一个实体
- `body2`: Body - 第二个实体

### 返回值
- `Body` - 布尔交运算后的实体

### 用途
保留两个实体的重叠部分，常用于创建复杂的几何约束或特殊形状。

### 示例
```python
from simplecadapi.operations import make_box, make_sphere, intersect

# 球体与立方体的交集
cube = make_box(10, 10, 10)
sphere = make_sphere(6)
rounded_cube = intersect(cube, sphere)

# 创建透镜形状
sphere1 = make_sphere(8)
sphere2 = make_sphere(8)  # 需要偏移位置
# lens_shape = intersect(sphere1, sphere2)  # 需要sphere2在不同位置

# 圆柱与立方体的交集（创建圆柱形孔的边界）
cutting_cylinder = make_cylinder(5, 20)
bounding_box = make_box(8, 8, 15)
bounded_cylinder = intersect(cutting_cylinder, bounding_box)
```

## 布尔运算的高级应用

### 复杂装配体建模
```python
def create_gear_tooth():
    """创建齿轮齿形"""
    # 基础齿形（简化）
    tooth_profile = make_rectangle(2, 5)
    tooth = extrude(tooth_profile, distance=3)
    
    # 添加圆角
    tooth_rounded = fillet(tooth, [], 0.2)
    return tooth_rounded

def create_simple_gear(radius, teeth_count, thickness):
    """创建简单齿轮"""
    # 基础圆盘
    base_circle = make_circle(radius)
    gear_base = extrude(base_circle, distance=thickness)
    
    # 中心孔
    center_hole = make_cylinder(radius * 0.3, thickness)
    gear_with_hole = cut(gear_base, center_hole)
    
    # 添加齿（简化处理，实际需要阵列操作）
    return gear_with_hole

# 组装齿轮系统
main_gear = create_simple_gear(15, 20, 5)
pinion_gear = create_simple_gear(8, 12, 5)
# gear_assembly = union(main_gear, pinion_gear)  # 需要调整位置
```

### 管道系统建模
```python
def create_pipe_junction():
    """创建管道三通接头"""
    # 主管道
    main_pipe = make_cylinder(4, 20)
    
    # 分支管道
    branch_pipe = make_cylinder(3, 15)
    
    # 合并形成三通
    junction = union(main_pipe, branch_pipe)
    
    # 创建内部空腔
    main_cavity = make_cylinder(3, 20)
    branch_cavity = make_cylinder(2, 15)
    total_cavity = union(main_cavity, branch_cavity)
    
    # 抽出空腔
    hollow_junction = cut(junction, total_cavity)
    
    return hollow_junction

pipe_junction = create_pipe_junction()
```

### 建筑构件建模
```python
def create_window_frame(width, height, frame_thickness, glass_thickness):
    """创建窗框"""
    # 外框
    outer_frame = make_box(width, frame_thickness, height)
    
    # 玻璃开口
    glass_opening = make_box(
        width - 2 * frame_thickness,
        glass_thickness,
        height - 2 * frame_thickness
    )
    
    # 切出玻璃槽
    frame_with_opening = cut(outer_frame, glass_opening)
    
    # 玻璃
    glass = make_box(
        width - 2 * frame_thickness - 0.5,  # 留0.5的间隙
        glass_thickness - 0.2,
        height - 2 * frame_thickness - 0.5
    )
    
    return frame_with_opening, glass

frame, glass = create_window_frame(100, 80, 5, 1)
```

### 机械零件建模
```python
def create_bearing_housing():
    """创建轴承座"""
    # 主体
    housing_body = make_box(40, 30, 20)
    
    # 轴承孔
    bearing_hole = make_cylinder(15, 20)
    housing_with_hole = cut(housing_body, bearing_hole)
    
    # 油槽
    oil_groove = make_cylinder(12, 2)
    housing_final = cut(housing_with_hole, oil_groove)
    
    # 安装孔
    mount_hole1 = make_cylinder(2, 20)
    mount_hole2 = make_cylinder(2, 20)
    # 需要在不同位置创建安装孔
    
    return housing_final

bearing_housing = create_bearing_housing()
```

### 错误处理和验证
```python
def safe_boolean_operation(operation, body1, body2):
    """安全的布尔运算"""
    # 验证输入
    if not body1.is_valid():
        raise ValueError("第一个实体无效")
    if not body2.is_valid():
        raise ValueError("第二个实体无效")
    
    try:
        result = operation(body1, body2)
        if not result.is_valid():
            raise ValueError("布尔运算结果无效")
        return result
    except Exception as e:
        print(f"布尔运算失败: {e}")
        return None

# 使用示例
box1 = make_box(10, 10, 10)
box2 = make_box(5, 5, 5)

safe_union = safe_boolean_operation(union, box1, box2)
safe_cut = safe_boolean_operation(cut, box1, box2)
safe_intersect = safe_boolean_operation(intersect, box1, box2)
```

### 批量布尔运算
```python
def union_all(bodies):
    """将多个实体全部合并"""
    if not bodies:
        return None
    if len(bodies) == 1:
        return bodies[0]
    
    result = bodies[0]
    for body in bodies[1:]:
        result = union(result, body)
        if not result.is_valid():
            raise ValueError("合并过程中产生无效实体")
    
    return result

def cut_all(target, cutters):
    """从目标实体中减去多个切割实体"""
    result = target
    for cutter in cutters:
        result = cut(result, cutter)
        if not result.is_valid():
            raise ValueError("切割过程中产生无效实体")
    
    return result

# 使用示例
base = make_box(50, 50, 10)
holes = [
    make_cylinder(2, 10),  # 需要在不同位置
    make_cylinder(2, 10),
    make_cylinder(2, 10),
    make_cylinder(2, 10)
]
perforated_plate = cut_all(base, holes)
```

## 最佳实践

### 1. 操作顺序优化
```python
# 好的做法：先做复杂的切割，再做简单的合并
def efficient_modeling():
    base = make_box(100, 50, 20)
    
    # 先做所有的切割操作
    hole1 = make_cylinder(5, 20)
    hole2 = make_cylinder(3, 20)
    base_cut = cut(cut(base, hole1), hole2)
    
    # 再添加附加特征
    boss = make_cylinder(8, 5)
    final_part = union(base_cut, boss)
    
    return final_part
```

### 2. 避免重复计算
```python
# 缓存中间结果
class PartBuilder:
    def __init__(self):
        self.base_part = None
        self.modified_part = None
    
    def get_base(self):
        if self.base_part is None:
            self.base_part = make_box(20, 20, 10)
        return self.base_part
    
    def add_hole(self, radius, depth):
        base = self.get_base()
        hole = make_cylinder(radius, depth)
        self.modified_part = cut(base, hole)
        return self.modified_part
```

## 注意事项
1. 确保参与运算的实体都是有效的
2. 布尔运算可能失败，特别是对于复杂几何体
3. 运算顺序可能影响最终结果和性能
4. 避免对过于接近或重叠的实体进行运算
5. 大型装配体应考虑分段处理
6. 某些极端情况下可能产生非流形几何体
7. 建议在关键步骤后验证实体的有效性
