# union_rsolid

## API定义

```python
def union_rsolid(solid1: Solid, solid2: Solid) -> Solid
```

*来源文件: operations.py*

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

## 返回值说明

Solid: 两个实体的并集结果，包含两个实体的所有体积

## 异常

- **ValueError**: 当输入实体无效或运算失败时抛出异常

## API使用例子

```python
# 创建两个重叠的立方体
box1 = make_box_rsolid(2, 2, 2, (0, 0, 0))
box2 = make_box_rsolid(2, 2, 2, (1, 0, 0))
# 计算并集
union_result = union_rsolid(box1, box2)
# 结果是一个组合的形状，体积小于两个立方体体积之和
# 圆柱和立方体的并集
cylinder = make_cylinder_rsolid(1.0, 3.0)
box = make_box_rsolid(1, 1, 1, (0, 0, 1))
combined = union_rsolid(cylinder, box)
```
