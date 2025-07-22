# sweep_rsolid

## API定义

```python
def sweep_rsolid(profile: Face, path: Wire, is_frenet: bool = False) -> Solid
```

## API作用

沿指定路径扫掠二维轮廓创建三维实体或壳体。常用于创建管道、导线、
复杂曲面等。Frenet框架控制轮廓在路径上的旋转行为。

## API参数说明

### profile

- **类型**: `Face`
- **说明**: 要扫掠的轮廓面，定义扫掠的横截面形状

### path

- **类型**: `Wire`
- **说明**: 扫掠路径线，定义轮廓沿其移动的路径

### is_frenet

- **类型**: `bool, optional`
- **说明**: 是否使用Frenet框架，默认为False。 True时轮廓沿路径的法向量旋转，False时保持轮廓方向

### 返回值

Union[Solid, Shell]: 扫掠后的实体或壳体，取决于make_solid参数

## 异常

- **ValueError**: 当轮廓、路径无效或扫掠操作失败时抛出异常
