# union_rsolidlist

## API Definition

```python
def union_rsolidlist(*solids: Union[Solid, Sequence[Solid]]) -> List[Solid]
```

*Source: operations.py*

## Description

实体列表并集运算

将一组实体尝试进行并集运算。任何可以通过并集连接成整体的实体
都会被融合成一个新的实体；无法连接的实体保持独立。该过程会一直
进行，直到没有新的实体可以被成功融合为止。

## Parameters

### *solids

- **Description**: 需要尝试并集的实体对象，可以传入： - 单个序列：union_rsolidlist([solid1, solid2, ...]) - 多个参数：union_rsolidlist(solid1, solid2, ...) - 混合输入：union_rsolidlist(solid1, [solid2, solid3], ...)，会自动展开所有序列

## Returns

List[Solid]: 并集运算后的实体列表。可以合并为整体的实体会被融合，
无法融合的实体会原样保留。

## Raises

- **ValueError**: 当输入列表无效或内部包含非Solid对象时抛出异常

## Examples

### Example 1
```python
# 创建三个实体，其中前两个接触可以融合，第三个独立
box1 = make_box_rsolid(2, 2, 2, (0, 0, 0))
box2 = make_box_rsolid(2, 2, 2, (1, 0, 0))
sphere = make_sphere_rsolid(1.0, (10, 0, 0))
```

### Example 2
```python
# 多种调用方式都支持且等价
union_results1 = union_rsolidlist([box1, box2, sphere])
union_results2 = union_rsolidlist(box1, box2, sphere)
union_results3 = union_rsolidlist(box1, [box2, sphere])
# union_results长度为2：一个融合后的立方体组合和一个独立的球体
```
