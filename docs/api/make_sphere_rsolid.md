# make_sphere_rsolid

## API Definition

```python
def make_sphere_rsolid(radius: float, center: Tuple[float, float, float] = (0, 0, 0)) -> Solid
```

*Source: operations.py*

## Description

创建球体并返回实体对象

创建球体实体，是基础的三维几何体之一。自动为球体的面添加标签（surface），
便于后续的面选择操作。体积等于(4/3)πr³。

## Parameters

### radius

- **Type**: `float`
- **Description**: 球体的半径，必须为正数

### center

- **Type**: `Tuple[float, float, float], optional`
- **Description**: 球体的中心坐标 (x, y, z)， 默认为 (0, 0, 0)

## Returns

Solid: 创建的实体对象，表示一个球体

## Raises

- **ValueError**: 当半径小于等于0时抛出异常

## Examples

### Example 1
```python
# 创建标准单位球体
unit_sphere = make_sphere_rsolid(1.0)
volume = unit_sphere.get_volume()  # 体积为(4/3)π≈4.19
```

### Example 2
```python
# 创建大球体
large_sphere = make_sphere_rsolid(3.0)
```

### Example 3
```python
# 创建偏移的球体
offset_sphere = make_sphere_rsolid(2.0, (1, 1, 1))
```

### Example 4
```python
# 获取球体的面进行后续操作
faces = unit_sphere.get_faces()
surface_faces = [f for f in faces if f.has_tag("surface")]
```
