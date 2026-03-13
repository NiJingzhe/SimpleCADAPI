# fillet_rsolid

## API Definition

```python
def fillet_rsolid(solid: Solid, edges: List[Edge], radius: float) -> Solid
```

*Source: operations.py*

## Description

对实体的边进行圆角操作

对实体的指定边进行圆角处理，创建平滑的过渡面。常用于消除尖锐边缘，
改善外观和减少应力集中。圆角半径不能太大，否则可能导致几何冲突。

## Parameters

### solid

- **Type**: `Solid`
- **Description**: 要进行圆角操作的实体对象

### edges

- **Type**: `List[Edge]`
- **Description**: 要进行圆角的边列表，通常从实体获取

### radius

- **Type**: `float`
- **Description**: 圆角半径，必须为正数，不能大于相邻面的最小尺寸

## Returns

Solid: 圆角后的实体对象

## Raises

- **ValueError**: 当圆角半径小于等于0或圆角操作失败时抛出异常

## Examples

### Example 1
```python
# 对立方体的所有边进行圆角
box = make_box_rsolid(4, 4, 4)
all_edges = box.get_edges()
rounded_box = fillet_rsolid(box, all_edges[:4], 0.5)  # 只对前4条边圆角
```

### Example 2
```python
# 对圆柱体的边进行圆角
cylinder = make_cylinder_rsolid(2.0, 5.0)
edges = cylinder.get_edges()
# 选择顶部和底部的圆边
circular_edges = [e for e in edges if e.has_tag("circular")]
rounded_cylinder = fillet_rsolid(cylinder, circular_edges, 0.3)
```

### Example 3
```python
# 对复杂几何体的特定边圆角
complex_solid = union_rsolidlist([box, cylinder])[0]
selected_edges = complex_solid.get_edges()[:6]
smoothed_solid = fillet_rsolid(complex_solid, selected_edges, 0.2)
```
