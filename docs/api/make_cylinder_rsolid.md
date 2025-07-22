# make_cylinder_rsolid

## API定义

```python
def make_cylinder_rsolid(radius: float, height: float, bottom_face_center: Tuple[float, float, float] = (0, 0, 0), axis: Tuple[float, float, float] = (0, 0, 1)) -> Solid
```

## API作用

创建圆柱体实体，是基础的三维几何体之一。自动为圆柱体的面添加标签
（top、bottom、cylindrical），便于后续的面选择操作。体积等于πr²h。

## API参数说明

### radius

- **类型**: `float`
- **说明**: 圆柱体的半径，必须为正数

### height

- **类型**: `float`
- **说明**: 圆柱体的高度，必须为正数

### bottom_face_center

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 圆柱体底面中心坐标 (x, y, z)， 默认为 (0, 0, 0)

### axis

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 圆柱体的轴向向量 (x, y, z)， 定义圆柱体的方向，默认为 (0, 0, 1) 表示沿Z轴方向

### 返回值

Solid: 创建的实体对象，表示一个圆柱体

## 异常

- **ValueError**: 当半径或高度小于等于0时抛出异常
