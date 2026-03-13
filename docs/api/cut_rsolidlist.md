# cut_rsolidlist

## API Definition

```python
def cut_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> List[Solid]
```

*Source: operations.py*

## Description

实体差集运算（布尔减法）

从第一个实体中依次减去其他实体的重叠部分，常用于创建孔洞、凹槽等。
结果实体的体积 = solid1体积 - (solid1∩solid2) - (结果∩solid3) - ...

## Parameters

### *solids

- **Description**: 需要进行差集运算的实体对象，可以传入： - 单个序列：cut_rsolidlist([solid1, solid2, ...]) - 多个参数：cut_rsolidlist(solid1, solid2, ...) - 混合输入：cut_rsolidlist(solid1, [solid2, solid3], ...)，会自动展开所有序列 第一个实体作为基础实体，后续实体依次从基础实体中减去。

## Returns

List[Solid]: 差集运算结果的实体列表。从第一个实体中依次减去其他所有实体。
返回包含结果的列表：[result_solid]

## Raises

- **ValueError**: 当输入实体无效或运算失败时抛出异常

## Examples

### Example 1
```python
# 在立方体中创建圆形孔（两种方式等价）
box = make_box_rsolid(4, 4, 4)
hole = make_cylinder_rsolid(1.0, 4.0)
result1 = cut_rsolidlist(box, hole)
result2 = cut_rsolidlist([box, hole])
```

### Example 2
```python
# 创建多个孔的结构
base = make_box_rsolid(6, 3, 2)
hole1 = make_cylinder_rsolid(0.5, 2, (1, 0, 0))
hole2 = make_cylinder_rsolid(0.5, 2, (5, 0, 0))
slotted_base = cut_rsolidlist(base, hole1, hole2)
```

### Example 3
```python
# 从球体中减去立方体
sphere = make_sphere_rsolid(2.0)
cube = make_box_rsolid(2, 2, 2)
carved_sphere = cut_rsolidlist(sphere, cube)
```
