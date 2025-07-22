# make_circle_rface

## API定义

```python
def make_circle_rface(center: Tuple[float, float, float], radius: float, normal: Tuple[float, float, float] = (0, 0, 1)) -> Face
```

## API作用

创建圆形面对象，用于构建实心圆形截面。可以用于拉伸、旋转等操作来创建
圆柱体、圆锥体等三维几何体。面积等于πr²。

## API参数说明

### center

- **类型**: `Tuple[float, float, float]`
- **说明**: 圆心坐标 (x, y, z)，定义圆的中心位置

### radius

- **类型**: `float`
- **说明**: 圆的半径，必须为正数

### normal

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 圆所在平面的法向量 (x, y, z)， 默认为 (0, 0, 1) 表示XY平面

### 返回值

Face: 创建的面对象，表示一个实心的圆形面

## 异常

- **ValueError**: 当半径小于等于0或其他参数无效时抛出异常
