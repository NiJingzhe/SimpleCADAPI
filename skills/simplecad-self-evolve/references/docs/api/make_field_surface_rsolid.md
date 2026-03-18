# make_field_surface_rsolid

## API Definition

```python
def make_field_surface_rsolid(field, bounds: Optional[Tuple[Tuple[float, float, float], Tuple[float, float, float]]] = None, resolution: Tuple[int, int, int] = (24, 24, 24), iso: float = 0.0, cap_bounds: bool = True) -> Solid
```

*Source: operations.py*

## Description

通过场函数等势面构建闭合曲面实体。

使用场函数定义隐式曲面，并抽取等势面生成闭合实体。

## Parameters

### field

- **Description**: 标量场对象（ScalarField）或可调用函数。

### bounds

- **Description**: 采样边界 (min_xyz, max_xyz)，可为 None（自动推导）。

### resolution

- **Description**: 采样分辨率 (nx, ny, nz)。

### iso

- **Description**: 等势面值。

### cap_bounds

- **Description**: 是否对边界裁切处进行封闭封口。

## Returns

Solid: 等势面闭合实体。

## Raises

- **ValueError**: 当采样失败或无法构建实体时抛出异常。

## Examples

```python
field = Field.make_sphere_rscalarfield((0, 0, 0), 1.0)
solid = make_field_surface_rsolid(field, ((-1.2, -1.2, -1.2), (1.2, 1.2, 1.2)))
```
