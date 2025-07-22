# make_sphere_rsolid

## API定义

```python
def make_sphere_rsolid(radius: float, center: Tuple[float, float, float] = (0, 0, 0)) -> Solid
```

## API作用

创建球体实体，是基础的三维几何体之一。自动为球体的面添加标签（surface），
便于后续的面选择操作。体积等于(4/3)πr³。

## API参数说明

### radius

- **类型**: `float`
- **说明**: 球体的半径，必须为正数

### center

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 球体的中心坐标 (x, y, z)， 默认为 (0, 0, 0)

### 返回值

Solid: 创建的实体对象，表示一个球体

## 异常

- **ValueError**: 当半径小于等于0时抛出异常
