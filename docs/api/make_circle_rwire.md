# make_circle_rwire

## API定义

```python
def make_circle_rwire(center: Tuple[float, float, float], radius: float, normal: Tuple[float, float, float] = (0, 0, 1)) -> Wire
```

## API作用

创建圆形线对象，用于构建封闭的圆形轮廓。与make_circle_redge不同，
此函数返回的是线对象，可以直接用于创建面或进行其他线操作。

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

Wire: 创建的线对象，表示一个完整的圆形轮廓

## 异常

- **ValueError**: 当半径小于等于0或其他参数无效时抛出异常
