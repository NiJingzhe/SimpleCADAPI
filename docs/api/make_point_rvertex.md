# make_point_rvertex

## API定义

```python
def make_point_rvertex(x: float, y: float, z: float) -> Vertex
```

## API作用

创建三维空间中的几何点，通常用作其他几何对象的构造参数，如作为线段的端点、
圆弧的控制点等。支持当前坐标系变换。

## API参数说明

### x

- **类型**: `float`
- **说明**: X坐标值，用于定义点在X轴方向的位置

### y

- **类型**: `float`
- **说明**: Y坐标值，用于定义点在Y轴方向的位置

### z

- **类型**: `float`
- **说明**: Z坐标值，用于定义点在Z轴方向的位置

### 返回值

Vertex: 创建的顶点对象，包含指定坐标的点

## 异常

- **ValueError**: 当坐标无效时抛出异常

## API使用例子

```python
...     local_point = make_point_rvertex(0, 0, 0)  # 实际位置为(1, 1, 1)
```
