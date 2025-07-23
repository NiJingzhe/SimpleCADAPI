# fillet_rsolid

## API定义

```python
def fillet_rsolid(solid: Solid, edges: List[Edge], radius: float) -> Solid
```

*来源文件: operations.py*

## API作用

对实体的指定边进行圆角处理，创建平滑的过渡面。常用于消除尖锐边缘，
改善外观和减少应力集中。圆角半径不能太大，否则可能导致几何冲突。

## API参数说明

### solid

- **类型**: `Solid`
- **说明**: 要进行圆角操作的实体对象

### edges

- **类型**: `List[Edge]`
- **说明**: 要进行圆角的边列表，通常从实体获取

### radius

- **类型**: `float`
- **说明**: 圆角半径，必须为正数，不能大于相邻面的最小尺寸

## 返回值说明

Solid: 圆角后的实体对象

## 异常

- **ValueError**: 当圆角半径小于等于0或圆角操作失败时抛出异常

## API使用例子

```python
# 对立方体的所有边进行圆角
box = make_box_rsolid(4, 4, 4)
all_edges = box.get_edges()
rounded_box = fillet_rsolid(box, all_edges[:4], 0.5)  # 只对前4条边圆角
# 对圆柱体的边进行圆角
cylinder = make_cylinder_rsolid(2.0, 5.0)
edges = cylinder.get_edges()
# 选择顶部和底部的圆边
circular_edges = [e for e in edges if e.has_tag("circular")]
rounded_cylinder = fillet_rsolid(cylinder, circular_edges, 0.3)
# 对复杂几何体的特定边圆角
complex_solid = union_rsolid(box, cylinder)
selected_edges = complex_solid.get_edges()[:6]
smoothed_solid = fillet_rsolid(complex_solid, selected_edges, 0.2)
```
