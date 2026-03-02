# make_cylinder_rsolid

## API定义

```python
def make_cylinder_rsolid(radius: float, height: float, bottom_face_center: Tuple[float, float, float] = (0, 0, 0), axis: Tuple[float, float, float] = (0, 0, 1)) -> Solid
```

*来源文件: operations.py*

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

## 返回值说明

Solid: 创建的实体对象，表示一个圆柱体

## 异常

- **ValueError**: 当半径或高度小于等于0时抛出异常

## API使用例子

```python
# 创建标准圆柱体
cylinder = make_cylinder_rsolid(2.0, 5.0)
volume = cylinder.get_volume()  # 体积为π×2²×5≈62.83
# 创建水平圆柱体
horizontal_cyl = make_cylinder_rsolid(radius=1.0, height=4.0, bottom_face_center=(0, 0, 0), axis=(1, 0, 0))
# 创建偏移的圆柱体,底面中心在(2, 2, 0)
offset_cyl = make_cylinder_rsolid(1.5, 3.0, (2, 2, 0))
# 获取圆柱体的面进行后续操作
faces = cylinder.get_faces()
top_faces = [f for f in faces if f.has_tag("top")]
```
