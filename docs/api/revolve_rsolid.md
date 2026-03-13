# revolve_rsolid

## API Definition

```python
def revolve_rsolid(profile: Union[Wire, Face], axis: Tuple[float, float, float] = (0, 0, 1), angle: float = 360, origin: Tuple[float, float, float] = (0, 0, 0)) -> Solid
```

*Source: operations.py*

## Description

围绕轴旋转轮廓创建实体

围绕指定轴旋转二维轮廓创建三维实体。常用于创建轴对称的几何体，
如圆柱体、圆锥体、球体等。如果输入是线，必须是封闭的线。

## Parameters

### profile

- **Type**: `Union[Wire, Face]`
- **Description**: 要旋转的轮廓，可以是封闭的线或面

### axis

- **Type**: `Tuple[float, float, float], optional`
- **Description**: 旋转轴向量 (x, y, z)， 定义旋转轴的方向，默认为 (0, 0, 1)

### angle

- **Type**: `float, optional`
- **Description**: 旋转角度，单位为度数（0-360）， 默认为360度（完整旋转），正值表示逆时针旋转

### origin

- **Type**: `Tuple[float, float, float], optional`
- **Description**: 旋转轴通过的点坐标 (x, y, z)， 默认为 (0, 0, 0), 由此我们知道，origin和axis可以求出转轴两点，一点是origin本身，另一点是origin+axis向量的终点

## Returns

Solid: 旋转后的实体对象

## Raises

- **ValueError**: 当轮廓不是封闭的线、角度小于等于0或其他参数无效时抛出异常

## Examples

### Example 1
```python
# 旋转矩形创建圆柱体
rect = make_rectangle_rface(1.0, 3.0, (2, 0, 0))  # 远离旋转轴
cylinder = revolve_rsolid(rect, (0, 0, 1), 360)
```

### Example 2
```python
# 创建圆锥体
triangle_points = [(1, 0, 0), (2, 0, 0), (1.5, 2, 0)]
triangle = make_polyline_rwire(triangle_points, closed=True)
cone = revolve_rsolid(triangle, (0, 0, 1), 360)
```

### Example 3
```python
# 创建部分旋转体（90度扇形）
rect = make_rectangle_rface(0.5, 2.0, (1.5, 0, 0))
partial_solid = revolve_rsolid(rect, (0, 0, 1), 90)
```
