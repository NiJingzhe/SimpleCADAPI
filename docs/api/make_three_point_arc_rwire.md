# make_three_point_arc_rwire

## API定义

```python
def make_three_point_arc_rwire(start: Tuple[float, float, float], middle: Tuple[float, float, float], end: Tuple[float, float, float]) -> Wire
```

## API作用

通过三个点创建圆弧线对象，与make_three_point_arc_redge功能相同，
但返回的是线对象，可以与其他线对象连接或用于构建复杂轮廓。

## API参数说明

### start

- **类型**: `Tuple[float, float, float]`
- **说明**: 圆弧的起始点坐标 (x, y, z)

### middle

- **类型**: `Tuple[float, float, float]`
- **说明**: 圆弧上的中间点坐标 (x, y, z)， 用于确定圆弧的曲率和方向

### end

- **类型**: `Tuple[float, float, float]`
- **说明**: 圆弧的结束点坐标 (x, y, z)

### 返回值

Wire: 创建的线对象，包含一个通过三点的圆弧

## 异常

- **ValueError**: 当三个点共线或坐标无效时抛出异常
