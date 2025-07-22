# union_rsolid

## API定义

```python
def union_rsolid(solid1: Solid, solid2: Solid) -> Solid
```

## API作用

计算两个实体的并集，返回包含两个实体所有体积的新实体。
并集运算会合并两个实体的重叠部分，结果体积大于等于任一输入实体。

## API参数说明

### solid1

- **类型**: `Solid`
- **说明**: 第一个参与运算的实体对象

### solid2

- **类型**: `Solid`
- **说明**: 第二个参与运算的实体对象

### 返回值

Solid: 两个实体的并集结果，包含两个实体的所有体积

## 异常

- **ValueError**: 当输入实体无效或运算失败时抛出异常
