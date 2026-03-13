# shell_rsolid

## API Definition

```python
def shell_rsolid(solid: Solid, faces_to_remove: List[Face], thickness: float) -> Solid
```

*Source: operations.py*

## Description

对实体进行抽壳操作，创建空心结构

将实体转换为空心结构，常用于创建容器、外壳等。通过移除指定面
创建开口，壁厚决定了外壳的厚度。如果不移除任何面则创建闭合空心体。

## Parameters

### solid

- **Type**: `Solid`
- **Description**: 要抽壳的实体对象

### faces_to_remove

- **Type**: `List[Face]`
- **Description**: 要移除的面列表，这些面将被开口， 如果为空列表则不移除任何面（闭合抽壳）

### thickness

- **Type**: `float`
- **Description**: 壁厚，必须为正数，定义抽壳后的壁厚度

## Returns

Solid: 抽壳后的实体对象，内部为空心结构

## Raises

- **ValueError**: 当壁厚小于等于0或抽壳操作失败时抛出异常

## Examples

### Example 1
```python
# 创建空心立方体容器
box = make_box_rsolid(4, 4, 4)
top_faces = [f for f in box.get_faces() if f.has_tag("top")]
container = shell_rsolid(box, top_faces, 0.2)
```

### Example 2
```python
# 创建空心球体
sphere = make_sphere_rsolid(3.0)
# 不移除任何面，创建闭合空心球
hollow_sphere = shell_rsolid(sphere, [], 0.3)
```

### Example 3
```python
# 创建有开口的圆柱体容器
cylinder = make_cylinder_rsolid(2.0, 5.0)
top_faces = [f for f in cylinder.get_faces() if f.has_tag("top")]
cup = shell_rsolid(cylinder, top_faces, 0.1)
```
