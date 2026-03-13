# chamfer_rsolid

## API Definition

```python
def chamfer_rsolid(solid: Solid, edges: List[Edge], distance: float) -> Solid
```

*Source: operations.py*

## Description

对实体的边进行倒角操作

对实体的指定边进行倒角处理，创建斜面过渡。与圆角不同，倒角创建的是
平面过渡而不是圆弧过渡。常用于机械零件的边缘处理，便于装配和安全。

## Parameters

### solid

- **Type**: `Solid`
- **Description**: 要进行倒角操作的实体对象

### edges

- **Type**: `List[Edge]`
- **Description**: 要进行倒角的边列表，通常从实体获取

### distance

- **Type**: `float`
- **Description**: 倒角距离，必须为正数，定义从边缘向内的倒角深度

## Returns

Solid: 倒角后的实体对象

## Raises

- **ValueError**: 当倒角距离小于等于0或倒角操作失败时抛出异常

## Examples

### Example 1
```python
# 对立方体的边进行倒角
box = make_box_rsolid(4, 4, 4)
edges = box.get_edges()
chamfered_box = chamfer_rsolid(box, edges[:4], 0.3)
```

### Example 2
```python
# 对圆柱体的边倒角
cylinder = make_cylinder_rsolid(2.0, 5.0)
cylinder_edges = cylinder.get_edges()
chamfered_cylinder = chamfer_rsolid(cylinder, cylinder_edges[:2], 0.2)
```

### Example 3
```python
# 选择性倒角
complex_solid = make_box_rsolid(6, 3, 2)
top_edges = [e for e in complex_solid.get_edges() if e.has_tag("top")]
chamfered_top = chamfer_rsolid(complex_solid, top_edges, 0.1)
```
