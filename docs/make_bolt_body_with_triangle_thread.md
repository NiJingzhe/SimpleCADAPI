# make_bolt_body_with_triangle_thread

## 描述
创建一个带有三角形螺纹的螺栓模型，包含圆柱形主体和螺旋三角形螺纹。

## 语法
```python
make_bolt_body_with_triangle_thread(
    length: float = 10.0,
    diameter: float = 2.0,
    thread_pitch: float = 0.5,
    thread_start: float = 2.0,
    thread_end: float = 10.0,
    thread_depth: float = 0.1,
) -> Body
```

## 参数
- **length** (float, optional): 螺栓总长度。默认值：10.0
- **diameter** (float, optional): 螺栓主体直径。默认值：2.0
- **thread_pitch** (float, optional): 螺纹螺距。默认值：0.5
- **thread_start** (float, optional): 螺纹起始位置（沿长度方向）。默认值：2.0
- **thread_end** (float, optional): 螺纹结束位置（沿长度方向）。默认值：10.0
- **thread_depth** (float, optional): 螺纹深度（三角形的高度）。默认值：0.1

## 返回值
- **Body**: 带三角形螺纹的螺栓实体

## 示例

### 基本螺栓
```python
from simplecadapi.advanced import *

# 创建标准螺栓
bolt = make_bolt_body_with_triangle_thread()

# 导出为STL文件
export_stl(bolt, "standard_bolt.stl")
```

### 自定义螺栓参数
```python
# 创建粗螺纹螺栓
coarse_bolt = make_bolt_body_with_triangle_thread(
    length=8.0,
    diameter=3.0,
    thread_pitch=1.0,       # 大螺距
    thread_start=1.0,
    thread_end=7.0,
    thread_depth=0.2        # 深螺纹
)

# 创建细螺纹螺栓
fine_bolt = make_bolt_body_with_triangle_thread(
    length=12.0,
    diameter=1.5,
    thread_pitch=0.25,      # 小螺距
    thread_start=0.5,
    thread_end=11.5,
    thread_depth=0.05       # 浅螺纹
)
```

### 不同规格螺栓对比
```python
# M6螺栓（模拟）
m6_bolt = make_bolt_body_with_triangle_thread(
    length=20.0,
    diameter=6.0,
    thread_pitch=1.0,
    thread_start=2.0,
    thread_end=18.0,
    thread_depth=0.15
)

# M3螺栓（模拟）
m3_bolt = make_bolt_body_with_triangle_thread(
    length=15.0,
    diameter=3.0,
    thread_pitch=0.5,
    thread_start=1.0,
    thread_end=14.0,
    thread_depth=0.08
)

# 并排放置
m6_bolt = translate_body(m6_bolt, vector=(-4.0, 0.0, 0.0))
m3_bolt = translate_body(m3_bolt, vector=(4.0, 0.0, 0.0))

bolt_comparison = union(m6_bolt, m3_bolt)
export_stl(bolt_comparison, "bolt_comparison.stl")
```

### 部分螺纹螺栓
```python
# 创建只在末端有螺纹的螺栓
partial_thread_bolt = make_bolt_body_with_triangle_thread(
    length=15.0,
    diameter=4.0,
    thread_pitch=0.7,
    thread_start=10.0,      # 螺纹从10mm开始
    thread_end=15.0,        # 到末端结束
    thread_depth=0.12
)

# 创建中段有螺纹的螺栓
middle_thread_bolt = make_bolt_body_with_triangle_thread(
    length=20.0,
    diameter=5.0,
    thread_pitch=0.8,
    thread_start=5.0,       # 螺纹从5mm开始
    thread_end=15.0,        # 到15mm结束
    thread_depth=0.15
)
```

### 螺栓装配示例
```python
# 创建螺栓
bolt = make_bolt_body_with_triangle_thread(
    length=25.0,
    diameter=4.0,
    thread_pitch=0.7,
    thread_start=3.0,
    thread_end=22.0,
    thread_depth=0.1
)

# 创建螺栓头部（六角头）
with LocalCoordinateSystem(
    origin=(0, 0, 25.0),
    x_axis=(1, 0, 0),
    y_axis=(0, 1, 0)
):
    # 简化为圆形头部
    head = make_cylinder(3.0, 2.0)

# 合并螺栓和头部
complete_bolt = union(bolt, head)

# 创建配套螺母孔（示例）
nut_block = make_box(8.0, 8.0, 4.0)
nut_hole = make_cylinder(2.1, 4.0)  # 略大于螺栓直径
nut = cut(nut_block, nut_hole)

# 将螺母放在适当位置
nut = translate_body(nut, vector=(15.0, 0.0, 0.0))

# 组合展示
bolt_assembly = union(complete_bolt, nut)
export_stl(bolt_assembly, "bolt_assembly.stl")
```

## 技术细节
- 螺栓主体为圆柱形，使用`make_cylinder`创建
- 螺纹使用三角形截面进行螺旋扫掠
- 三角形截面的底边等于`thread_pitch`，高度等于`thread_depth`
- 螺纹通过`helical_sweep`在指定区域内生成
- 最终通过布尔并运算将主体和螺纹合并

## 螺纹参数说明
- **thread_pitch**: 相邻螺纹峰之间的距离
- **thread_depth**: 螺纹的径向深度
- **thread_start/end**: 定义螺纹的轴向范围

## 应用场景
- 机械设计中的紧固件
- 教学演示模型
- 3D打印螺栓原型
- 装配体建模

## 注意事项
- `thread_start` 必须小于 `thread_end`
- `thread_depth` 不应超过 `diameter/4`，避免螺纹过深
- 螺纹区域应在螺栓长度范围内
- 高精度螺纹会增加计算时间和文件大小
- 螺栓沿Z轴正方向生成

## 制造考虑
- 实际制造时螺纹通常是螺旋切削形成的
- 3D打印时可能需要调整螺纹参数以适应打印精度
- 对于功能性螺栓，建议使用标准螺纹规格

## 相关函数
- [make_cylinder](make_cylinder.md) - 创建圆柱体
- [helical_sweep](helical_sweep.md) - 螺旋扫掠操作
- [union](union.md) - 布尔并运算
- [translate_body](translate_body.md) - 平移操作
