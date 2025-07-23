# make_wire_from_edges_rwire

## API定义

```python
def make_wire_from_edges_rwire(edges: List[Edge]) -> Wire
```

*来源文件: operations.py*

## API作用

将多个边对象连接成一个连续的线对象。边的顺序很重要，相邻的边应该
能够连接在一起。用于构建复杂的线框结构。

## API参数说明

### edges

- **类型**: `List[Edge]`
- **说明**: 输入的边对象列表，边应该能够连接成连续的线

## 返回值说明

Wire: 创建的线对象，由输入的边组成的连续线

## 异常

- **ValueError**: 当边列表为空或边无法连接时抛出异常

## API使用例子

```python
# 创建L形线
edge1 = make_line_redge((0, 0, 0), (2, 0, 0))  # 水平线
edge2 = make_line_redge((2, 0, 0), (2, 2, 0))  # 垂直线
l_wire = make_wire_from_edges_rwire([edge1, edge2])
# 创建包含直线和圆弧的复杂线
line = make_line_redge((0, 0, 0), (2, 0, 0))
arc = make_three_point_arc_redge((2, 0, 0), (3, 1, 0), (2, 2, 0))
complex_wire = make_wire_from_edges_rwire([line, arc])
```
