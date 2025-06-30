# LocalCoordinateSystem 类文档

## 概述
LocalCoordinateSystem是一个上下文管理器类，用于临时切换到指定的局部坐标系。它使用Python的`with`语句来管理坐标系的切换，确保在代码块执行完毕后自动恢复原来的坐标系。

## 类定义
```python
class LocalCoordinateSystem:
    """局部坐标系上下文管理器"""
```

## 构造函数
```python
def __init__(self, 
             origin: Tuple[float, float, float], 
             x_axis: Tuple[float, float, float], 
             y_axis: Tuple[float, float, float])
```

### 参数
- `origin`: 新坐标系的原点位置
- `x_axis`: 新坐标系的X轴方向
- `y_axis`: 新坐标系的Y轴方向

## 属性
- `cs`: CoordinateSystem对象，封装的坐标系

## 方法

### __enter__()
进入上下文时的操作
- 将新坐标系压入坐标系栈
- **返回**: CoordinateSystem对象

### __exit__(exc_type, exc_val, exc_tb)
退出上下文时的操作
- 从坐标系栈中弹出当前坐标系
- 自动恢复到上一个坐标系

## 相关函数

### get_current_cs() -> CoordinateSystem
获取当前活动的坐标系
- **返回**: 当前坐标系对象
- 从全局坐标系栈的顶部获取

## 使用示例

### 基本用法
```python
from simplecadapi.core import LocalCoordinateSystem, get_current_cs
from simplecadapi.operations import make_point

# 查看默认坐标系
print(f"默认坐标系: {get_current_cs()}")

# 使用局部坐标系
with LocalCoordinateSystem(
    origin=(10, 5, 0),
    x_axis=(1, 0, 0),
    y_axis=(0, 1, 0)
) as local_cs:
    print(f"局部坐标系: {get_current_cs()}")
    
    # 在局部坐标系中创建点
    point = make_point(1, 1, 0)  # 局部坐标(1,1,0)
    print(f"点的全局坐标: {point.global_coords}")  # 应该是(11,6,0)

# 自动恢复到原坐标系
print(f"恢复后的坐标系: {get_current_cs()}")
```

### 嵌套坐标系
```python
from simplecadapi.operations import make_rectangle

# 第一层局部坐标系
with LocalCoordinateSystem(
    origin=(10, 0, 0),
    x_axis=(1, 0, 0),
    y_axis=(0, 1, 0)
) as cs1:
    print(f"第一层坐标系原点: {get_current_cs().origin}")
    
    # 嵌套第二层局部坐标系
    with LocalCoordinateSystem(
        origin=(0, 10, 0),   # 相对于cs1的偏移
        x_axis=(0, 1, 0),    # 90度旋转
        y_axis=(-1, 0, 0)
    ) as cs2:
        print(f"第二层坐标系原点: {get_current_cs().origin}")
        
        # 在嵌套坐标系中创建几何体
        rect = make_rectangle(5, 3)
        
    print(f"退出第二层，当前坐标系: {get_current_cs().origin}")
    
print(f"完全退出，当前坐标系: {get_current_cs().origin}")
```

### 在不同坐标系中创建几何体
```python
from simplecadapi.operations import make_box, extrude
from simplecadapi.core import LocalCoordinateSystem

# 创建多个在不同坐标系中的立方体
boxes = []

# 第一个立方体：默认坐标系
box1 = make_box(2, 2, 2)
boxes.append(("默认坐标系", box1))

# 第二个立方体：平移坐标系
with LocalCoordinateSystem(
    origin=(5, 0, 0),
    x_axis=(1, 0, 0),
    y_axis=(0, 1, 0)
):
    box2 = make_box(2, 2, 2)
    boxes.append(("平移坐标系", box2))

# 第三个立方体：旋转坐标系
with LocalCoordinateSystem(
    origin=(0, 5, 0),
    x_axis=(0, 1, 0),     # X轴指向Y方向
    y_axis=(-1, 0, 0)     # Y轴指向-X方向
):
    box3 = make_box(2, 2, 2)
    boxes.append(("旋转坐标系", box3))

for name, box in boxes:
    print(f"{name}中的立方体: {box}")
```

### 倾斜平面上的草图
```python
from simplecadapi.operations import make_circle, extrude
import math

# 创建倾斜45度的坐标系
angle = math.pi / 4  # 45度
with LocalCoordinateSystem(
    origin=(0, 0, 0),
    x_axis=(1, 0, 0),
    y_axis=(0, math.cos(angle), math.sin(angle))  # 倾斜的Y轴
):
    # 在倾斜平面上创建圆形草图
    circle_sketch = make_circle(3)
    
    # 垂直拉伸（相对于倾斜平面）
    cylinder = extrude(circle_sketch, distance=5)
    print(f"倾斜圆柱体: {cylinder}")
```

### 复杂装配中的坐标系管理
```python
def create_component_at_position(pos, orientation):
    """在指定位置和方向创建组件"""
    x_axis, y_axis = orientation
    
    with LocalCoordinateSystem(pos, x_axis, y_axis):
        # 组件由多个基础几何体组成
        base = make_box(4, 4, 1)
        
        # 在组件坐标系中继续操作
        with LocalCoordinateSystem(
            origin=(0, 0, 1),
            x_axis=(1, 0, 0),
            y_axis=(0, 1, 0)
        ):
            pillar = make_cylinder(0.5, 3)
            
        return base, pillar

# 创建多个组件
components = []

# 组件1：原点位置，默认方向
comp1 = create_component_at_position(
    (0, 0, 0), 
    ((1, 0, 0), (0, 1, 0))
)
components.append(comp1)

# 组件2：平移位置，旋转方向
comp2 = create_component_at_position(
    (10, 0, 0),
    ((0, 1, 0), (-1, 0, 0))  # 90度旋转
)
components.append(comp2)

print(f"创建了 {len(components)} 个组件")
```

### 坐标系栈的手动管理（不推荐）
```python
from simplecadapi.core import _current_cs, CoordinateSystem

# 查看当前坐标系栈深度
print(f"坐标系栈深度: {len(_current_cs)}")

# 手动创建坐标系（不推荐，请使用with语句）
manual_cs = CoordinateSystem(origin=(5, 5, 5))

# 注意：直接操作_current_cs是不安全的
# _current_cs.append(manual_cs)  # 不推荐
# # 进行操作...
# _current_cs.pop()  # 容易忘记，导致栈不平衡

# 推荐使用with语句
with LocalCoordinateSystem(origin=(5, 5, 5), x_axis=(1, 0, 0), y_axis=(0, 1, 0)):
    # 安全的坐标系切换
    pass
```

### 异常处理中的坐标系管理
```python
def safe_operation_in_local_cs():
    """演示异常情况下坐标系的正确恢复"""
    print(f"操作前坐标系: {get_current_cs().origin}")
    
    try:
        with LocalCoordinateSystem(
            origin=(100, 100, 100),
            x_axis=(1, 0, 0),
            y_axis=(0, 1, 0)
        ):
            print(f"局部坐标系: {get_current_cs().origin}")
            
            # 模拟可能抛出异常的操作
            if True:  # 修改为False可以避免异常
                raise ValueError("模拟操作失败")
                
            # 正常的几何操作
            box = make_box(1, 1, 1)
            return box
            
    except ValueError as e:
        print(f"捕获异常: {e}")
        return None
    
    finally:
        # with语句确保即使发生异常也能正确恢复坐标系
        print(f"操作后坐标系: {get_current_cs().origin}")

# 测试异常安全性
result = safe_operation_in_local_cs()
print(f"最终坐标系: {get_current_cs().origin}")  # 应该是默认坐标系
```

## 注意事项
1. 总是使用`with`语句来确保坐标系的正确恢复
2. 支持任意深度的嵌套坐标系
3. 异常安全：即使发生异常也会正确恢复坐标系
4. 不要直接操作`_current_cs`列表，使用上下文管理器
5. 局部坐标系中创建的所有几何体都会自动转换到全局坐标系
6. 坐标系的切换不影响已创建的几何体
7. 嵌套坐标系的变换是累积的（相对变换）
