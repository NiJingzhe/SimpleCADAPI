# intersect_rsolidlist

## API Definition

```python
def intersect_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> List[Solid]
```

*Source: operations.py*

## Description

实体交集运算（布尔交集）

计算多个实体的交集，返回只包含所有实体重叠部分的新实体列表。
如果多个实体不相交，可能返回空列表。交集体积小于等于任一输入实体。

## Parameters

### *solids

- **Description**: 需要进行交集运算的实体对象，可以传入： - 单个序列：intersect_rsolidlist([solid1, solid2, ...]) - 多个参数：intersect_rsolidlist(solid1, solid2, ...) - 混合输入：intersect_rsolidlist(solid1, [solid2, solid3], ...)，会自动展开所有序列

## Returns

List[Solid]: 交集运算结果的实体列表。所有输入实体的共同交集部分。
如果没有有效的交集，返回空列表。

## Raises

- **ValueError**: 当输入实体无效或运算失败时抛出异常

## Examples

### Example 1
```python
# 计算多个实体的交集（两个方式等价）
box1 = make_box_rsolid(3, 3, 3, (0, 0, 0))
box2 = make_box_rsolid(3, 3, 3, (1, 1, 0))
sphere = make_sphere_rsolid(2.5)
intersection1 = intersect_rsolidlist([box1, box2, sphere])
intersection2 = intersect_rsolidlist(box1, box2, sphere)
# 两种调用方式等价
```

### Example 2
```python
# 球体和立方体的交集
sphere = make_sphere_rsolid(2.0)
cube = make_box_rsolid(3, 3, 3)
rounded_cube = intersect_rsolidlist(sphere, cube)
```

### Example 3
```python
# 三个实体的交集
cylinder = make_cylinder_rsolid(1.5, 4.0)
slab = make_box_rsolid(4, 4, 2, (0, 0, 1))
intersection = intersect_rsolidlist(cylinder, slab, sphere)
```
