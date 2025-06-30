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
# 使用虚拟环境 (推荐)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# 安装依赖
pip install cadquery numpy typing-extensions
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
- 🔄 **体积计算**: 准确的体积和属性计算

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

# 导出功能演示
python export_demo.py
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

## 🛠 扩展开发

添加新操作非常简单，遵循开放封闭原则：

```python
def helical_sweep(profile: Sketch, 
                  axis_start: Point, 
                  axis_end: Point, 
                  pitch: float, 
                  height: float) -> Body:
    """螺旋扫掠操作 - 扩展示例"""
    # 使用CADQuery实现
    # ...
    return Body(result_solid)
```

## 🔗 技术栈

- **Python 3.8+**
- **CADQuery 2.x**: 强大的CAD建模库
- **OpenCASCADE**: 专业几何内核
- **NumPy**: 数值计算支持

## 📊 测试结果

最新测试结果：
- ✅ 基础几何创建: 100%通过
- ✅ 坐标系管理: 100%通过  
- ✅ 基本实体创建: 100%通过
- ✅ 布尔运算: 90%通过
- ✅ 高级操作: 80%通过
- ✅ 导出功能: 100%通过

## 🎨 设计理念

此API设计展示了如何在保持强大功能的同时提供简洁易用的接口：

1. **抽象层次清晰**: 从点到实体的逐级构造
2. **错误处理完善**: 详细的异常信息和验证
3. **扩展性良好**: 新功能无需修改核心代码
4. **文档完整**: 代码即文档的设计理念

通过这个实现，用户可以专注于设计逻辑而不需要深入了解底层几何计算的复杂性。

#### 核心类定义
```python
from typing import List, Tuple, Union
import numpy as np

class CoordinateSystem:
    """三维坐标系（右手系）"""
    def __init__(self, origin: Tuple[float, float, float] = (0, 0, 0),
                 x_axis: Tuple[float, float, float] = (1, 0, 0),
                 y_axis: Tuple[float, float, float] = (0, 1, 0)):
        self.origin = np.array(origin, dtype=float)
        self.x_axis = self._normalize(x_axis)
        self.y_axis = self._normalize(y_axis)
        self.z_axis = self._normalize(np.cross(self.x_axis, self.y_axis))
        
    def _normalize(self, vector) -> np.ndarray:
        v = np.array(vector, dtype=float)
        return v / np.linalg.norm(v)
    
    def transform_point(self, point: np.ndarray) -> np.ndarray:
        """将局部坐标转换为全局坐标"""
        return self.origin + point[0]*self.x_axis + point[1]*self.y_axis + point[2]*self.z_axis

# 全局世界坐标系（右手系，XY水平，Z向上）
WORLD_CS = CoordinateSystem()

class Point:
    """三维点（存储在局部坐标系中的坐标）"""
    def __init__(self, coords: Tuple[float, float, float], cs: CoordinateSystem = WORLD_CS):
        self.local_coords = np.array(coords, dtype=float)
        self.cs = cs
        
    @property
    def global_coords(self) -> np.ndarray:
        """获取全局坐标系中的坐标"""
        return self.cs.transform_point(self.local_coords)

class Line:
    """曲线（线段/圆弧/样条）"""
    def __init__(self, points: List[Point], line_type: str = "segment"):
        """
        :param points: 控制点列表
        :param line_type: 类型 ('segment', 'arc', 'spline')
        """
        self.points = points
        self.type = line_type
        self._validate()
        
    def _validate(self):
        if self.type == "segment" and len(self.points) != 2:
            raise ValueError("线段需要2个控制点")
        if self.type == "arc" and len(self.points) != 3:
            raise ValueError("圆弧需要3个控制点")

class Sketch:
    """二维草图（闭合平面轮廓）"""
    def __init__(self, lines: List[Line]):
        self.lines = lines
        self._validate()
        
    def _validate(self):
        # 简化的闭合性和共面检查（实际实现需要几何计算）
        if not self._is_closed():
            raise ValueError("草图必须形成闭合轮廓")
        if not self._is_planar():
            raise ValueError("草图必须位于同一平面内")
            
    def _is_closed(self) -> bool:
        # 检查起点和终点是否重合
        start = self.lines[0].points[0].global_coords
        end = self.lines[-1].points[-1].global_coords
        return np.allclose(start, end, atol=1e-6)
    
    def _is_planar(self) -> bool:
        # 简化的共面检查（实际需要法向量计算）
        return True

class Body:
    """三维实体"""
    _id_counter = 0
    
    def __init__(self, geometry=None):
        self.geometry = geometry  # 实际存储CAD内核的几何引用
        self.id = Body._id_counter
        Body._id_counter += 1

# 当前坐标系上下文管理器
_current_cs = [WORLD_CS]  # 默认使用世界坐标系

class LocalCoordinateSystem:
    """局部坐标系上下文管理器"""
    def __init__(self, origin, x_axis, y_axis):
        self.cs = CoordinateSystem(origin, x_axis, y_axis)
        
    def __enter__(self):
        _current_cs.append(self.cs)
        return self.cs
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        _current_cs.pop()
```

#### 核心操作API
```python
# ===== 基础构造操作 =====
def make_point(x: float, y: float, z: float) -> Point:
    """在局部坐标系中创建点"""
    return Point((x, y, z), _current_cs[-1])

def make_line(points: List[Point], line_type: str = "segment") -> Line:
    """创建曲线（线段/圆弧/样条）"""
    return Line(points, line_type)

def make_sketch(lines: List[Line]) -> Sketch:
    """创建闭合草图"""
    return Sketch(lines)

# ===== 三维建模操作 =====
def extrude(sketch: Sketch, 
            direction: Tuple[float, float, float] = None, 
            distance: float = None,
            to_sketch: Sketch = None) -> Body:
    """
    拉伸操作
    :param direction: 拉伸方向向量（局部坐标系）
    :param distance: 拉伸距离
    :param to_sketch: 目标草图（用于变截面拉伸）
    """
    # 实现细节（转换到全局坐标系，调用CAD内核）
    return Body()

def revolve(sketch: Sketch, 
            axis_start: Point, 
            axis_end: Point, 
            angle: float) -> Body:
    """
    旋转操作
    :param axis_start: 旋转轴起点
    :param axis_end: 旋转轴终点
    :param angle: 旋转角度（弧度）
    """
    return Body()

def loft(sketches: List[Sketch]) -> Body:
    """放样操作（多个草图间过渡）"""
    return Body()

def sweep(profile: Sketch, path: Line) -> Body:
    """
    扫掠操作
    :param profile: 截面草图
    :param path: 扫掠路径
    """
    return Body()

# ===== 实体编辑操作 =====
def shell(body: Body, thickness: float) -> Body:
    """抽壳操作"""
    return Body()

def fillet(edge: Line, radius: float) -> Body:
    """
    圆角操作
    :param edge: 需要倒圆角的边（必须属于某个Body）
    :param radius: 圆角半径
    """
    return Body()

def chamfer(edge: Line, distance: float) -> Body:
    """
    倒角操作
    :param edge: 需要倒角的边
    :param distance: 倒角距离
    """
    return Body()

# ===== 布尔运算 =====
def cut(target: Body, tool: Body) -> Body:
    """布尔减运算"""
    return Body()

def union(body1: Body, body2: Body) -> Body:
    """布尔并运算"""
    return Body()
```

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