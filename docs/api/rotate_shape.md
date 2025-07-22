# rotate_shape

## API定义

```python
def rotate_shape(shape: AnyShape, angle: float, axis: Tuple[float, float, float] = (0, 0, 1), origin: Tuple[float, float, float] = (0, 0, 0)) -> AnyShape
```

## API作用

围绕指定轴和中心点旋转几何体，不改变几何体的形状和大小。
旋转操作支持当前坐标系变换，适用于所有类型的几何对象。
角度使用度数制，正值表示右手定则的逆时针旋转。

## API参数说明

### shape

- **类型**: `AnyShape`
- **说明**: 要旋转的几何体，可以是点、边、线、面、实体等任意几何对象

### angle

- **类型**: `float`
- **说明**: 旋转角度，单位为度数（0-360），正值表示逆时针旋转

### axis

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 旋转轴向量 (x, y, z)， 默认为 (0, 0, 1) 表示绕Z轴旋转

### origin

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 旋转中心点坐标 (x, y, z)， 默认为 (0, 0, 0)

### 返回值

AnyShape: 旋转后的几何体，类型与输入相同

## 异常

- **ValueError**: 当几何体或旋转参数无效时抛出异常
