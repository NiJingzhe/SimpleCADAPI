# make_round_spring

## 描述
创建一个圆形截面的螺旋弹簧模型。

## 语法
```python
make_round_spring(
    coil_radius: float = 1.0,
    string_radius: float = 0.1,
    pitch: float = 0.5,
    turns: int = 5,
) -> Body
```

## 参数
- **coil_radius** (float, optional): 弹簧的螺旋半径。默认值：1.0
- **string_radius** (float, optional): 弹簧丝的半径（圆形截面半径）。默认值：0.1
- **pitch** (float, optional): 螺距（每圈沿轴方向的距离）。默认值：0.5
- **turns** (int, optional): 弹簧圈数。默认值：5

## 返回值
- **Body**: 圆形弹簧实体

## 示例

### 基本圆形弹簧
```python
from simplecadapi.advanced import *

# 创建标准圆形弹簧
spring = make_round_spring()

# 导出为STL文件
export_stl(spring, "standard_spring.stl")
```

### 自定义参数弹簧
```python
# 创建大型弹簧
large_spring = make_round_spring(
    coil_radius=2.0,     # 较大的螺旋半径
    string_radius=0.2,   # 较粗的弹簧丝
    pitch=1.0,           # 较大的螺距
    turns=3              # 较少的圈数
)

# 创建精密弹簧
precision_spring = make_round_spring(
    coil_radius=0.5,     # 较小的螺旋半径
    string_radius=0.05,  # 较细的弹簧丝
    pitch=0.2,           # 较小的螺距
    turns=10             # 较多的圈数
)
```

### 不同规格的弹簧对比
```python
# 紧密弹簧（小螺距）
tight_spring = make_round_spring(
    coil_radius=1.0,
    string_radius=0.08,
    pitch=0.3,
    turns=8
)

# 疏松弹簧（大螺距）
loose_spring = make_round_spring(
    coil_radius=1.0,
    string_radius=0.08,
    pitch=0.8,
    turns=4
)

# 在不同位置放置
tight_spring = translate_body(tight_spring, vector=(-2.0, 0.0, 0.0))
loose_spring = translate_body(loose_spring, vector=(2.0, 0.0, 0.0))

# 合并展示
spring_comparison = union(tight_spring, loose_spring)
export_stl(spring_comparison, "spring_comparison.stl")
```

### 弹簧组合装配
```python
# 创建多个不同尺寸的弹簧
springs = []

for i in range(3):
    spring = make_round_spring(
        coil_radius=0.5 + i * 0.3,
        string_radius=0.05 + i * 0.02,
        pitch=0.3 + i * 0.1,
        turns=5 + i * 2
    )
    # 沿X轴排列
    spring = translate_body(spring, vector=(i * 2.0, 0.0, 0.0))
    springs.append(spring)

# 合并所有弹簧
spring_assembly = springs[0]
for s in springs[1:]:
    spring_assembly = union(spring_assembly, s)

export_stl(spring_assembly, "spring_assembly.stl")
```

## 技术细节
- 使用高精度螺旋扫掠（20点/圈）
- 截面为完美圆形
- 支持平滑spline路径
- 自动处理坐标系转换

## 应用场景
- 机械设计中的弹簧元件
- 减震器模型
- 玩具弹簧
- 教学演示模型

## 注意事项
- `string_radius` 不应超过 `coil_radius` 的一半，否则可能产生自相交
- `pitch` 值太小可能导致圈与圈之间重叠
- `turns` 必须为正整数
- 弹簧沿Z轴方向生成

## 相关函数
- [make_square_spring](make_square_spring.md) - 方形截面弹簧
- [make_bolt_body_with_triangle_thread](make_bolt_body_with_triangle_thread.md) - 螺纹螺栓
- [helical_sweep](helical_sweep.md) - 螺旋扫掠操作
