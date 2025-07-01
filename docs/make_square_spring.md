# make_square_spring

## 描述
创建一个方形截面的螺旋弹簧模型。

## 语法
```python
make_square_spring(
    coil_radius: float = 1.0,
    string_radius: float = 0.1,
    pitch: float = 0.5,
    turns: int = 5,
) -> Body
```

## 参数
- **coil_radius** (float, optional): 弹簧的螺旋半径。默认值：1.0
- **string_radius** (float, optional): 弹簧丝的"半径"（实际上是方形截面的半边长）。默认值：0.1
- **pitch** (float, optional): 螺距（每圈沿轴方向的距离）。默认值：0.5
- **turns** (int, optional): 弹簧圈数。默认值：5

## 返回值
- **Body**: 方形截面弹簧实体

## 示例

### 基本方形弹簧
```python
from simplecadapi.advanced import *

# 创建标准方形弹簧
square_spring = make_square_spring()

# 导出为STL文件
export_stl(square_spring, "square_spring.stl")
```

### 自定义参数弹簧
```python
# 创建粗壮的方形弹簧
heavy_spring = make_square_spring(
    coil_radius=1.5,     # 较大的螺旋半径
    string_radius=0.15,  # 较粗的弹簧丝
    pitch=0.8,           # 较大的螺距
    turns=4              # 4圈
)

# 创建精密方形弹簧
fine_spring = make_square_spring(
    coil_radius=0.8,     # 较小的螺旋半径
    string_radius=0.06,  # 较细的弹簧丝
    pitch=0.25,          # 较小的螺距
    turns=8              # 较多的圈数
)
```

### 方形弹簧与圆形弹簧对比
```python
# 创建相同参数的方形和圆形弹簧
common_params = {
    'coil_radius': 1.0,
    'string_radius': 0.1,
    'pitch': 0.5,
    'turns': 5
}

square_spring = make_square_spring(**common_params)
round_spring = make_round_spring(**common_params)

# 分别放置
square_spring = translate_body(square_spring, vector=(-1.5, 0.0, 0.0))
round_spring = translate_body(round_spring, vector=(1.5, 0.0, 0.0))

# 合并对比
spring_comparison = union(square_spring, round_spring)
export_stl(spring_comparison, "square_vs_round_spring.stl")
```

### 不同尺寸的方形弹簧阵列
```python
# 创建3x3的方形弹簧阵列
springs = []

for i in range(3):
    for j in range(3):
        spring = make_square_spring(
            coil_radius=0.6,
            string_radius=0.04 + (i + j) * 0.01,  # 渐变的截面尺寸
            pitch=0.3,
            turns=3 + i + j  # 渐变的圈数
        )
        # 在网格中排列
        spring = translate_body(spring, vector=(i * 1.5, j * 1.5, 0.0))
        springs.append(spring)

# 合并所有弹簧
spring_array = springs[0]
for s in springs[1:]:
    spring_array = union(spring_array, s)

export_stl(spring_array, "square_spring_array.stl")
```

### 装饰性方形弹簧
```python
# 创建装饰性的方形弹簧
decorative_spring = make_square_spring(
    coil_radius=2.0,
    string_radius=0.2,
    pitch=1.2,
    turns=3
)

# 添加底座
base = make_cylinder(2.5, 0.3)
base = translate_body(base, vector=(0.0, 0.0, -0.15))

# 组合
decorative_model = union(decorative_spring, base)
export_stl(decorative_model, "decorative_square_spring.stl")
```

## 技术细节
- 截面为正方形，边长为 `string_radius * 2`
- 使用高精度螺旋扫掠（20点/圈）
- 支持平滑spline路径
- 自动处理坐标系转换

## 方形 vs 圆形截面的特点
- **方形截面**：
  - 更高的抗扭刚度
  - 更大的接触面积
  - 独特的视觉效果
  - 更适合某些工程应用

- **圆形截面**：
  - 更低的应力集中
  - 更好的疲劳性能
  - 传统的弹簧设计

## 应用场景
- 特殊工程弹簧
- 装饰性弹簧元件
- 教学对比模型
- 艺术设计元素

## 注意事项
- `string_radius` 实际上定义的是方形截面的半边长
- 方形截面的弹簧可能在某些角度看起来有锯齿状边缘
- 截面尺寸不应超过螺旋间距，避免自相交
- 弹簧沿Z轴方向生成

## 相关函数
- [make_round_spring](make_round_spring.md) - 圆形截面弹簧
- [make_rectangle](make_rectangle.md) - 创建矩形截面
- [helical_sweep](helical_sweep.md) - 螺旋扫掠操作
