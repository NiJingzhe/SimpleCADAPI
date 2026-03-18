# helical_sweep_rsolid

## API Definition

```python
def helical_sweep_rsolid(profile: Wire, pitch: float, height: float, radius: float, center: Tuple[float, float, float] = (0, 0, 0), dir: Tuple[float, float, float] = (0, 0, 1)) -> Solid
```

*Source: operations.py*

## Description

沿螺旋路径扫掠轮廓创建实体

沿螺旋路径扫掠二维轮廓创建三维实体，常用于创建螺纹、弹簧、
螺旋管道等具有螺旋特征的几何体。轮廓必须是封闭的。

函数会自动矫正profile的朝向和位置：
- 确保profile的法向量朝向X轴正方向或负方向
- 将profile移动到距离旋转中心指定半径的位置

## Parameters

### profile

- **Type**: `Wire`
- **Description**: 要扫掠的轮廓线，必须是封闭的线轮廓

### pitch

- **Type**: `float`
- **Description**: 螺距，每转一圈在轴向上的距离，必须为正数

### height

- **Type**: `float`
- **Description**: 螺旋的总高度，必须为正数

### radius

- **Type**: `float`
- **Description**: 螺旋的半径，必须为正数

### center

- **Type**: `Tuple[float, float, float], optional`
- **Description**: 螺旋中心点坐标 (x, y, z)， 默认为 (0, 0, 0)

### dir

- **Type**: `Tuple[float, float, float], optional`
- **Description**: 螺旋轴方向向量 (x, y, z)， 默认为 (0, 0, 1) 表示沿Z轴方向

## Returns

Solid: 螺旋扫掠后的实体对象

## Raises

- **ValueError**: 当轮廓不封闭、螺距/高度/半径无效或扫掠失败时抛出异常

## Examples

### Example 1
```python
# 创建螺旋弹簧
circle_profile = make_circle_rwire((0, 0, 0), 0.2)
spring = helical_sweep_rsolid(circle_profile, 1.0, 10.0, 2.0)
```

### Example 2
```python
# 创建方形截面的螺旋管
square_profile = make_rectangle_rwire(0.5, 0.5)
square_helix = helical_sweep_rsolid(square_profile, 2.0, 8.0, 1.5)
```

### Example 3
```python
# 创建紧密螺旋结构
small_circle = make_circle_rwire((0, 0, 0), 0.1)
tight_helix = helical_sweep_rsolid(small_circle, 0.5, 5.0, 1.0)
```
