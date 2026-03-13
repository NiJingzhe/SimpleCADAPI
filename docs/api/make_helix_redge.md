# make_helix_redge

## API Definition

```python
def make_helix_redge(pitch: float, height: float, radius: float, center: Tuple[float, float, float] = (0, 0, 0), dir: Tuple[float, float, float] = (0, 0, 1)) -> Edge
```

*Source: operations.py*

## Description

创建螺旋线并返回边对象

创建螺旋线边对象，用于构建螺旋形状的路径或进行螺旋扫掠。
螺旋线绕指定轴旋转，同时沿轴向移动，形成螺旋形状。

## Parameters

### pitch

- **Type**: `float`
- **Description**: 螺距，每转一圈在轴向上的距离，必须为正数

### height

- **Type**: `float`
- **Description**: 螺旋线的总高度，必须为正数

### radius

- **Type**: `float`
- **Description**: 螺旋线的半径，必须为正数

### center

- **Type**: `Tuple[float, float, float], optional`
- **Description**: 螺旋线的中心点坐标 (x, y, z)， 默认为 (0, 0, 0)

### dir

- **Type**: `Tuple[float, float, float], optional`
- **Description**: 螺旋轴的方向向量 (x, y, z)， 默认为 (0, 0, 1) 表示沿Z轴方向

## Returns

Edge: 创建的边对象，表示一个螺旋线

## Raises

- **ValueError**: 当螺距、高度或半径小于等于0时抛出异常

## Examples

### Example 1
```python
# 创建标准螺旋线
helix = make_helix_redge(2.0, 10.0, 1.0)  # 螺距2，高度10，半径1
```

### Example 2
```python
# 创建紧密螺旋线
tight_helix = make_helix_redge(0.5, 5.0, 0.5)
```

### Example 3
```python
# 创建水平螺旋线
horizontal_helix = make_helix_redge(1.0, 8.0, 2.0, (0, 0, 0), (1, 0, 0))
```
