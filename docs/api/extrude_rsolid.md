# extrude_rsolid

## API定义

```python
def extrude_rsolid(profile: Union[Wire, Face], direction: Tuple[float, float, float], distance: float) -> Solid
```

## API作用

沿指定方向拉伸二维轮廓创建三维实体。如果输入是线，必须是封闭的线；
如果输入是面，直接进行拉伸。这是创建柱状、管状等规则几何体的基础操作。

## API参数说明

### profile

- **类型**: `Union[Wire, Face]`
- **说明**: 要拉伸的轮廓，可以是封闭的线或面

### direction

- **类型**: `Tuple[float, float, float]`
- **说明**: 拉伸方向向量 (x, y, z)， 定义拉伸的方向，会被标准化处理

### distance

- **类型**: `float`
- **说明**: 拉伸距离，必须为正数

### 返回值

Solid: 拉伸后的实体对象

## 异常

- **ValueError**: 当轮廓不是封闭的线、距离小于等于0或其他参数无效时抛出异常
