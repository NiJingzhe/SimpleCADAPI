# make_helix_rwire

## API定义

```python
def make_helix_rwire(pitch: float, height: float, radius: float, center: Tuple[float, float, float] = (0, 0, 0), dir: Tuple[float, float, float] = (0, 0, 1)) -> Wire
```

## API作用

创建螺旋线线对象，与make_helix_redge功能相同但返回线对象。
可以用于后续的扫掠操作或作为复杂路径的一部分。

## API参数说明

### pitch

- **类型**: `float`
- **说明**: 螺距，每转一圈在轴向上的距离，必须为正数

### height

- **类型**: `float`
- **说明**: 螺旋线的总高度，必须为正数

### radius

- **类型**: `float`
- **说明**: 螺旋线的半径，必须为正数

### center

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 螺旋线的中心点坐标 (x, y, z)， 默认为 (0, 0, 0)

### dir

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 螺旋轴的方向向量 (x, y, z)， 默认为 (0, 0, 1) 表示沿Z轴方向

### 返回值

Wire: 创建的线对象，包含一个螺旋线

## 异常

- **ValueError**: 当螺距、高度或半径小于等于0时抛出异常
