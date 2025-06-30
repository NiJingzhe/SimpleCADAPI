# 便利函数文档

## 概述
便利函数提供了快速创建常用三维几何体的方法，无需手动创建草图再进行拉伸操作。

---

## make_box

### 函数签名
```python
def make_box(width: float, height: float, depth: float, center: bool = True) -> Body
```

### 参数
- `width`: float - 立方体的宽度（X方向）
- `height`: float - 立方体的高度（Y方向）
- `depth`: float - 立方体的深度（Z方向）
- `center`: bool - 是否以原点为中心，默认True

### 返回值
- `Body` - 立方体实体对象

### 用途
快速创建矩形立方体，是最常用的基础几何体。

### 示例
```python
from simplecadapi.operations import make_box

# 创建中心对齐的立方体
centered_box = make_box(10, 8, 6)

# 创建从原点开始的立方体
corner_box = make_box(10, 8, 6, center=False)

# 创建正方体
cube = make_box(5, 5, 5)

# 创建薄板
thin_plate = make_box(50, 30, 2)

# 在特定坐标系中创建
with LocalCoordinateSystem(origin=(10, 10, 5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    offset_box = make_box(4, 4, 4)
```

---

## make_cylinder

### 函数签名
```python
def make_cylinder(radius: float, height: float) -> Body
```

### 参数
- `radius`: float - 圆柱体半径
- `height`: float - 圆柱体高度

### 返回值
- `Body` - 圆柱体实体对象

### 用途
创建圆柱形实体，常用于轴、孔、管道等。

### 示例
```python
from simplecadapi.operations import make_cylinder

# 创建标准圆柱
cylinder = make_cylinder(5, 10)

# 创建细长的轴
shaft = make_cylinder(1, 50)

# 创建扁平的圆盘
disk = make_cylinder(20, 2)

# 创建不同尺寸的圆柱用于布尔运算
outer_cylinder = make_cylinder(8, 15)
inner_cylinder = make_cylinder(6, 15)
# tube = cut(outer_cylinder, inner_cylinder)  # 创建管子

# 在倾斜坐标系中创建圆柱
import math
angle = math.pi / 6  # 30度
with LocalCoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(1, 0, 0),
    y_axis=(0, math.cos(angle), math.sin(angle))
):
    tilted_cylinder = make_cylinder(3, 12)
```

---

## make_sphere

### 函数签名
```python
def make_sphere(radius: float) -> Body
```

### 参数
- `radius`: float - 球体半径

### 返回值
- `Body` - 球体实体对象

### 用途
创建球形实体，常用于轴承、装饰元素或布尔运算。

### 示例
```python
from simplecadapi.operations import make_sphere

# 创建标准球体
sphere = make_sphere(5)

# 创建小球
bead = make_sphere(0.5)

# 创建大球
large_sphere = make_sphere(25)

# 球体在布尔运算中的应用
base_cube = make_box(10, 10, 10)
cutting_sphere = make_sphere(6)
rounded_cube = intersect(base_cube, cutting_sphere)

# 创建多个球体的组合
def create_molecule():
    """创建分子模型"""
    # 中心原子
    center_atom = make_sphere(1.5)
    
    # 周围原子（需要在不同位置创建）
    # 这里只是示例，实际需要在不同坐标系中创建
    satellite_atom = make_sphere(1.0)
    
    return center_atom, satellite_atom

center, satellite = create_molecule()
```

## 便利函数的高级应用

### 参数化建模
```python
def create_parametric_flange(outer_radius, inner_radius, thickness, bolt_count, bolt_radius):
    """创建参数化法兰"""
    # 主体圆盘
    flange_body = make_cylinder(outer_radius, thickness)
    
    # 中心孔
    center_hole = make_cylinder(inner_radius, thickness)
    flange_with_hole = cut(flange_body, center_hole)
    
    # 螺栓孔（简化处理，实际需要阵列）
    bolt_hole = make_cylinder(bolt_radius, thickness)
    # 需要在圆周上创建多个螺栓孔
    
    return flange_with_hole

# 创建不同规格的法兰
small_flange = create_parametric_flange(50, 20, 10, 4, 3)
large_flange = create_parametric_flange(100, 40, 15, 8, 5)
```

### 快速原型制作
```python
def quick_prototype(length, width, height, corner_radius=0):
    """快速创建原型零件"""
    # 基础形状
    base = make_box(length, width, height)
    
    if corner_radius > 0:
        # 添加圆角
        base = fillet(base, [], corner_radius)
    
    return base

# 创建一系列原型
prototypes = [
    quick_prototype(20, 15, 10, 1),   # 小型零件
    quick_prototype(50, 30, 25, 2),   # 中型零件
    quick_prototype(100, 80, 40, 5),  # 大型零件
]
```

### 标准件库
```python
class StandardParts:
    """标准件库"""
    
    @staticmethod
    def iso_bolt_head(diameter, height):
        """ISO标准螺栓头"""
        # 六角头简化为圆柱体
        head_radius = diameter * 0.8
        return make_cylinder(head_radius, height)
    
    @staticmethod
    def din_washer(inner_diameter, outer_diameter, thickness):
        """DIN标准垫圈"""
        outer_disk = make_cylinder(outer_diameter/2, thickness)
        inner_hole = make_cylinder(inner_diameter/2, thickness)
        return cut(outer_disk, inner_hole)
    
    @staticmethod
    def bearing_ball(size):
        """标准轴承滚珠"""
        return make_sphere(size/2)

# 使用标准件
bolt_head = StandardParts.iso_bolt_head(8, 5)
washer = StandardParts.din_washer(8.5, 16, 1.5)
ball_bearing = StandardParts.bearing_ball(6)
```

### 建筑构件
```python
def create_brick(length=200, width=100, height=50):
    """创建标准砖块"""
    return make_box(length, width, height, center=False)

def create_column(radius, height, base_radius=None):
    """创建圆柱"""
    if base_radius is None:
        base_radius = radius * 1.2
    
    # 柱身
    column_shaft = make_cylinder(radius, height)
    
    # 柱基
    column_base = make_cylinder(base_radius, height * 0.1)
    
    # 组合
    return union(column_shaft, column_base)

# 建筑元素
brick = create_brick()
column = create_column(15, 300)
```

### 机械零件
```python
def create_shaft(diameter, length, keyway_width=None, keyway_depth=None):
    """创建轴"""
    shaft = make_cylinder(diameter/2, length)
    
    if keyway_width and keyway_depth:
        # 添加键槽
        keyway = make_box(keyway_width, diameter, keyway_depth)
        shaft = cut(shaft, keyway)
    
    return shaft

def create_gear_blank(outer_diameter, inner_diameter, thickness):
    """创建齿轮毛坯"""
    outer_disk = make_cylinder(outer_diameter/2, thickness)
    inner_hole = make_cylinder(inner_diameter/2, thickness)
    return cut(outer_disk, inner_hole)

# 机械零件
main_shaft = create_shaft(20, 100, 6, 3)
gear_blank = create_gear_blank(80, 25, 12)
```

### 容器和包装
```python
def create_box_container(length, width, height, wall_thickness):
    """创建盒状容器"""
    # 外壳
    outer_box = make_box(length, width, height, center=False)
    
    # 内腔
    inner_length = length - 2 * wall_thickness
    inner_width = width - 2 * wall_thickness
    inner_height = height - wall_thickness  # 顶部开口
    
    with LocalCoordinateSystem(
        origin=(wall_thickness, wall_thickness, wall_thickness),
        x_axis=(1, 0, 0),
        y_axis=(0, 1, 0)
    ):
        inner_cavity = make_box(inner_length, inner_width, inner_height, center=False)
    
    return cut(outer_box, inner_cavity)

def create_cylindrical_container(diameter, height, wall_thickness):
    """创建圆柱形容器"""
    outer_cylinder = make_cylinder(diameter/2, height)
    inner_cylinder = make_cylinder(diameter/2 - wall_thickness, height - wall_thickness)
    
    # 需要偏移内圆柱的位置
    return cut(outer_cylinder, inner_cylinder)

# 容器
storage_box = create_box_container(100, 80, 60, 3)
cylindrical_tank = create_cylindrical_container(50, 100, 5)
```

### 测试和验证
```python
def test_convenience_functions():
    """测试便利函数"""
    test_results = []
    
    # 测试立方体
    try:
        box = make_box(10, 10, 10)
        test_results.append(("make_box", box.is_valid()))
    except Exception as e:
        test_results.append(("make_box", f"Failed: {e}"))
    
    # 测试圆柱
    try:
        cylinder = make_cylinder(5, 10)
        test_results.append(("make_cylinder", cylinder.is_valid()))
    except Exception as e:
        test_results.append(("make_cylinder", f"Failed: {e}"))
    
    # 测试球体
    try:
        sphere = make_sphere(5)
        test_results.append(("make_sphere", sphere.is_valid()))
    except Exception as e:
        test_results.append(("make_sphere", f"Failed: {e}"))
    
    return test_results

# 运行测试
test_results = test_convenience_functions()
for func_name, result in test_results:
    print(f"{func_name}: {result}")
```

### 批量创建
```python
def create_bolt_series():
    """创建系列螺栓"""
    diameters = [6, 8, 10, 12, 16, 20]
    bolts = {}
    
    for d in diameters:
        head_height = d * 0.7
        head = make_cylinder(d * 0.8, head_height)
        
        shaft_length = d * 5
        shaft = make_cylinder(d/2, shaft_length)
        
        # 组合螺栓头和螺杆
        bolt = union(head, shaft)
        bolts[f"M{d}"] = bolt
    
    return bolts

# 创建螺栓系列
bolt_series = create_bolt_series()
```

## 性能优化建议

### 避免重复创建
```python
# 缓存常用几何体
class GeometryCache:
    def __init__(self):
        self._cache = {}
    
    def get_box(self, width, height, depth, center=True):
        key = (width, height, depth, center)
        if key not in self._cache:
            self._cache[key] = make_box(width, height, depth, center)
        return self._cache[key]

cache = GeometryCache()
box1 = cache.get_box(10, 10, 10)
box2 = cache.get_box(10, 10, 10)  # 从缓存获取
```

### 合理的参数范围
```python
def validated_make_box(width, height, depth, center=True):
    """带参数验证的立方体创建"""
    if any(dim <= 0 for dim in [width, height, depth]):
        raise ValueError("所有尺寸必须为正数")
    
    if any(dim > 1000 for dim in [width, height, depth]):
        print("警告：创建的几何体很大，可能影响性能")
    
    return make_box(width, height, depth, center)
```

## 注意事项
1. 所有便利函数都在当前坐标系中创建几何体
2. 立方体的center参数影响几何体的定位方式
3. 圆柱体总是沿Z轴方向创建
4. 球体总是以原点为中心创建
5. 所有函数返回的都是有效的Body对象
6. 对于复杂形状，建议组合使用便利函数和布尔运算
7. 在循环中创建大量几何体时注意性能
