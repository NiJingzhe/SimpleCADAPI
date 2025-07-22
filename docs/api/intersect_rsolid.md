# intersect_rsolid

## API定义

```python
def intersect_rsolid(solid1: Solid, solid2: Solid) -> Solid
```

## API作用

计算两个实体的交集，返回只包含两个实体重叠部分的新实体。
如果两个实体不相交，可能返回空实体。交集体积小于等于任一输入实体。

## API参数说明

### solid1

- **类型**: `Solid`
- **说明**: 第一个参与运算的实体对象

### solid2

- **类型**: `Solid`
- **说明**: 第二个参与运算的实体对象

### 返回值

Solid: 两个实体的交集结果，只包含两个实体的重叠部分

## 异常

- **ValueError**: 当输入实体无效或运算失败时抛出异常
