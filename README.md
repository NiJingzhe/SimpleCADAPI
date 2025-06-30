### CAD建模形式化Python API设计与实现

使用CADQuery作为底层实现的简化CAD API

## 🎯 项目概述

本项目实现了一套简化的CAD建模Python API，基于README中设计的核心理念：

- **开放封闭原则(OCP)**: 核心几何类封闭修改，操作函数开放扩展
- **显式坐标系管理**: 通过上下文管理器实现局部/全局坐标系转换
- **类型安全**: 点→线→草图→实体的严格类型递进
- **可扩展性**: 基于CADQuery的强大底层，提供简洁的高层API

## 🚀 快速开始

### 安装依赖

```bash
# 安装依赖
uv sync
```

### 基础使用示例

```python
from simplecadapi import *

# 创建基本几何
p1 = make_point(0, 0, 0)
p2 = make_point(1, 1, 0)
line = make_line([p1, p2])

# 创建实体
box = make_box(2.0, 1.0, 0.5)
cylinder = make_cylinder(0.5, 2.0)
sphere = make_sphere(1.0)

# 布尔运算
result = union(box, cylinder)

# 局部坐标系
with LocalCoordinateSystem(origin=(10, 5, 0), 
                         x_axis=(0, 1, 0), 
                         y_axis=(-1, 0, 0)):
    local_box = make_box(1.0, 1.0, 1.0)
    # 自动转换为全局坐标系
```

## 📁 项目结构

```
SimpleCADAPI/
├── src/
│   └── simplecadapi/
│       ├── __init__.py      # API导出
│       ├── core.py          # 核心几何类
│       └── operations.py    # 建模操作函数
├── test/
│   ├── comprehensive_test.py # 主要测试套件
│   ├── archive/             # 历史测试文件
│   └── README.md           # 测试说明
├── output/                 # 测试输出目录
├── docs/                   # API文档
├── USAGE.md               # 详细使用指南
└── README.md              # 项目说明
```

## ✅ 实现状态

### 已实现功能

- ✅ **核心几何类**: Point, Line, Sketch, Body
- ✅ **坐标系管理**: LocalCoordinateSystem上下文管理器
- ✅ **基础构造**: make_point, make_line, make_rectangle, make_circle
- ✅ **基本实体**: make_box, make_cylinder, make_sphere
- ✅ **三维建模**: extrude, revolve, loft, sweep
- ✅ **螺旋扫掠**: helical_sweep (Profile-based API)
- ✅ **布尔运算**: union, cut, intersect
- ✅ **高级操作**: pattern_linear, pattern_2d, fillet, chamfer, shell
- ✅ **模型导出**: STL, STEP格式导出
- ✅ **完整测试**: comprehensive_test.py 包含45+个测试用例

### 需要优化的功能

- 🔄 **建模操作**: extrude, revolve, loft, sweep (CADQuery集成需优化)
- 🔄 **实体编辑**: 边选择和复杂编辑操作

## 🧪 运行测试

```bash
# 主要测试套件（推荐）
python test/comprehensive_test.py

# 包含所有功能的全面测试：
# - 基础建模操作（拉伸、旋转、放样、扫掠）
# - 高级操作（阵列、圆角、倒角、抽壳）
# - 布尔运算（并、减、交）
# - 螺旋扫掠（圆形、螺纹齿形、三角形截面）
# - 复杂零件构建（法兰、齿轮、装配体）
# - 坐标系操作验证

# 测试输出将生成45+个STL/STEP文件到output/目录
```

## 📖 使用文档

查看 [USAGE.md](USAGE.md) 获取详细的使用指南和API参考。

## 🎯 设计特点

### 1. 开放封闭原则 (OCP)

```python
# 核心类保持稳定
class Point, Line, Sketch, Body  # 封闭修改

# 新操作通过独立函数扩展
def my_custom_operation(body: Body, param: float) -> Body:
    # 实现新功能，不修改核心类
    return Body(result)
```

### 2. 显式坐标系管理

```python
# 全局坐标系
p1 = make_point(1, 2, 3)

# 局部坐标系 (自动转换)
with LocalCoordinateSystem(origin=(10, 5, 0), 
                         x_axis=(0, 1, 0), 
                         y_axis=(-1, 0, 0)):
    p2 = make_point(0, 0, 0)  # 实际位置 (10, 5, 0)
```

### 3. 类型安全递进

```python
Point → Line → Sketch → Body
```

每个层级都有严格的类型检查和验证。


## 🔗 技术栈

- **Python 3.10+**
- **CADQuery 2.x**: 强大的CAD建模库
- **OpenCASCADE**: 专业几何内核
- **NumPy**: 数值计算支持


## 🎨 设计理念

此API设计展示了如何在保持强大功能的同时提供简洁易用的接口：

1. **抽象层次清晰**: 从点到实体的逐级构造
2. **错误处理完善**: 详细的异常信息和验证
3. **扩展性良好**: 新功能无需修改核心代码
4. **文档完整**: 代码即文档的设计理念

通过这个实现，用户可以专注于设计逻辑而不需要深入了解底层几何计算的复杂性。

### OCP（开放封闭原则）实现方案
1. **核心几何类封闭**：
   - `Point`, `Line`, `Sketch`, `Body` 保持稳定不修改
   - 新增操作通过独立函数实现，不修改类内部

2. **操作扩展开放**：
   ```python
   # 扩展新操作示例：螺旋扫掠
   def helical_sweep(profile: Sketch, 
                    axis_start: Point, 
                    axis_end: Point, 
                    pitch: float, 
                    height: float) -> Body:
       """螺旋扫掠操作"""
       # 实现细节（不影响现有类）
       return Body()
   
   # 扩展新操作示例：阵列
   def pattern_linear(body: Body, 
                     direction: Tuple[float, float, float], 
                     count: int, 
                     spacing: float) -> Body:
       """线性阵列"""
       return Body()
   ```

3. **坐标系处理**：
   ```python
   # 使用示例
   with LocalCoordinateSystem(origin=(10, 5, 0), 
                             x_axis=(0, 1, 0), 
                             y_axis=(-1, 0, 0)) as local_cs:
       
       # 在局部坐标系中创建点（Y轴是全局X的反方向）
       p1 = make_point(0, 0, 0)  # 全局位置 (10, 5, 0)
       p2 = make_point(3, 2, 0)  # 全局位置 (10-2, 5+3, 0) = (8, 8, 0)
       
       # 创建线段
       line = make_line([p1, p2])
       
       # 创建草图
       rect_sketch = make_sketch([...])
       
       # 在局部坐标系中拉伸（沿局部Z轴）
       body = extrude(rect_sketch, direction=(0, 0, 1), distance=5)
   ```

### 关键设计特点
1. **显式坐标系管理**：
   - 通过`LocalCoordinateSystem`上下文管理器切换当前坐标系
   - 所有坐标参数自动使用当前局部坐标系

2. **几何类型严格分离**：
   - 点→线→草图→实体的递进构造关系
   - 草图必须闭合且共面

3. **操作与数据分离**：
   - 所有建模操作均为独立函数（非类方法）
   - 符合"动词+名词"命名规范（`make_point`, `extrude`等）

4. **全局坐标系基准**：
   - 所有几何最终转换到`WORLD_CS`进行运算
   - 局部坐标系只影响参数输入

5. **可扩展性**：
   - 新增操作无需修改核心类
   - 支持自定义坐标系变换规则

此设计提供了清晰的几何构造流程和灵活的坐标系管理，同时满足开放封闭原则，便于扩展新的建模操作和算法实现。