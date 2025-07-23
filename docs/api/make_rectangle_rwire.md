# make_rectangle_rwire

## API定义

```python
def make_rectangle_rwire(width: float, height: float, center: Tuple[float, float, float] = (0, 0, 0), normal: Tuple[float, float, float] = (0, 0, 1)) -> Wire
```

*来源文件: operations.py*

## API作用

创建矩形线对象，用于构建矩形轮廓。矩形以指定中心点为中心，在指定平面内
创建。可以用于构建复杂的多边形轮廓或作为拉伸的基础轮廓。

## API参数说明

### width

- **类型**: `float`
- **说明**: 矩形的宽度，必须为正数

### height

- **类型**: `float`
- **说明**: 矩形的高度，必须为正数

### center

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 矩形中心坐标 (x, y, z)， 默认为 (0, 0, 0)

### normal

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 矩形所在平面的法向量 (x, y, z)， 默认为 (0, 0, 1) 表示XY平面

## 返回值说明

Wire: 创建的线对象，表示一个封闭的矩形轮廓

## 异常

- **ValueError**: 当宽度或高度小于等于0或其他参数无效时抛出异常

## API使用例子

```python
# 创建标准矩形轮廓
rect = make_rectangle_rwire(4.0, 3.0)
# 创建偏移的矩形
offset_rect = make_rectangle_rwire(2.0, 2.0, (1, 1, 0))
# 创建垂直平面上的矩形
vertical_rect = make_rectangle_rwire(3.0, 2.0, (0, 0, 0), (1, 0, 0))
```
