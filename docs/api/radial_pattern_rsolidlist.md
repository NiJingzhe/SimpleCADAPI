# radial_pattern_rsolidlist

## API定义

```python
def radial_pattern_rsolidlist(shape: AnyShape, center: Tuple[float, float, float], axis: Tuple[float, float, float], count: int, total_rotation_angle: float) -> List[Solid]
```

## API作用

围绕指定轴创建几何体的径向阵列，生成等角度间隔的旋转排列。
常用于创建齿轮、花瓣、螺栓圆形分布等对称结构。

## API参数说明

### shape

- **类型**: `AnyShape`
- **说明**: 要阵列的几何体，可以是任意类型的几何对象

### center

- **类型**: `Tuple[float, float, float]`
- **说明**: 旋转中心点坐标 (x, y, z)

### axis

- **类型**: `Tuple[float, float, float]`
- **说明**: 旋转轴向量 (x, y, z)，定义旋转轴方向

### count

- **类型**: `int`
- **说明**: 阵列数量，必须为正整数，包括原始对象

### total_rotation_angle

- **类型**: `float`
- **说明**: 总旋转角度，单位为度数（0-360）， 定义整个阵列的角度范围

### 返回值

List[Solid]: 径向阵列后的几何体列表，包含原始对象和所有旋转的对象

## 异常

- **ValueError**: 当阵列数量小于等于0或角度无效时抛出异常
