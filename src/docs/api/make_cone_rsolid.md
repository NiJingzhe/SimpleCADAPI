# make_cone_rsolid

## API定义

```python
def make_cone_rsolid(bottom_radius: float, height: float, top_radius: float = 0.0, bottom_face_center: Tuple[float, float, float] = (0, 0, 0), axis: Tuple[float, float, float] = (0, 0, 1)) -> Solid
```

*来源文件: operations.py*

## API作用

创建圆锥体实体，是基础的三维几何体之一。自动为圆锥体的面添加标签
（top、bottom、conical），便于后续的面选择操作。

## API参数说明

### bottom_radius

- **类型**: `float`
- **说明**: 圆锥体的底面半径，必须为正数

### height

- **类型**: `float`
- **说明**: 圆锥体的高度，必须为正数

### top_radius

- **类型**: `float, optional`
- **说明**: 圆锥体的顶面半径，默认为0.0（尖锥）

### bottom_face_center

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 圆锥体底面中心坐标 (x, y, z)， 默认为 (0, 0, 0)

### axis

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 圆锥体的轴向向量 (x, y, z)， 定义圆锥体的方向，默认为 (0, 0, 1) 表示沿Z轴方向

## 返回值说明

Solid: 创建的实体对象，表示一个圆锥体

## 异常

- **ValueError**: 当半径或高度小于等于0时抛出异常

## API使用例子

```python
# 创建标准圆锥体（尖锥）
cone = make_cone_rsolid(2.0, 5.0)
volume = cone.get_volume()  # 体积为(1/3)π×2²×5≈20.94
# 创建截锥体
truncated_cone = make_cone_rsolid(3.0, 4.0, 1.0)
```
