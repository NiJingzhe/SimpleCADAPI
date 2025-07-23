# make_box_rsolid

## API定义

```python
def make_box_rsolid(width: float, height: float, depth: float, bottom_face_center: Tuple[float, float, float] = (0, 0, 0)) -> Solid
```

*来源文件: operations.py*

## API作用

创建矩形立方体实体，是最基础的三维几何体之一。自动为立方体的面添加
标签（top、bottom、front、back、left、right），便于后续的面选择操作。
体积等于width×height×depth。

## API参数说明

### width

- **类型**: `float`
- **说明**: 立方体的宽度（X方向尺寸），必须为正数

### height

- **类型**: `float`
- **说明**: 立方体的高度（Y方向尺寸），必须为正数

### depth

- **类型**: `float`
- **说明**: 立方体的深度（Z方向尺寸），必须为正数

### bottom_face_center

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 立方体的底面中心坐标 (x, y, z)， 默认为 (0, 0, 0)，注意这里的中心是立方体底面的中心点

## 返回值说明

Solid: 创建的实体对象，表示一个立方体

## 异常

- **ValueError**: 当宽度、高度或深度小于等于0时抛出异常

## API使用例子

```python
# 创建标准单位立方体
unit_cube = make_box_rsolid(1.0, 1.0, 1.0)
volume = unit_cube.get_volume()  # 体积为1
# 创建矩形立方体
rect_box = make_box_rsolid(4.0, 2.0, 3.0)
# 创建偏移的立方体
offset_box = make_box_rsolid(2.0, 2.0, 2.0, (1, 1, 1))
# 获取立方体的面进行后续操作
faces = unit_cube.get_faces()
top_faces = [f for f in faces if f.has_tag("top")]
```
