# revolve_rsolid

## API定义

```python
def revolve_rsolid(profile: Union[Wire, Face], axis: Tuple[float, float, float] = (0, 0, 1), angle: float = 360, origin: Tuple[float, float, float] = (0, 0, 0)) -> Solid
```

## API作用

围绕指定轴旋转二维轮廓创建三维实体。常用于创建轴对称的几何体，
如圆柱体、圆锥体、球体等。如果输入是线，必须是封闭的线。

## API参数说明

### profile

- **类型**: `Union[Wire, Face]`
- **说明**: 要旋转的轮廓，可以是封闭的线或面

### axis

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 旋转轴向量 (x, y, z)， 定义旋转轴的方向，默认为 (0, 0, 1)

### angle

- **类型**: `float, optional`
- **说明**: 旋转角度，单位为度数（0-360）， 默认为360度（完整旋转），正值表示逆时针旋转

### origin

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 旋转轴通过的点坐标 (x, y, z)， 默认为 (0, 0, 0), 由此我们知道，origin和axis可以求出转轴两点，一点是origin本身，另一点是origin+axis向量的终点

### 返回值

Solid: 旋转后的实体对象

## 异常

- **ValueError**: 当轮廓不是封闭的线、角度小于等于0或其他参数无效时抛出异常
