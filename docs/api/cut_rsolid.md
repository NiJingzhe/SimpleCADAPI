# cut_rsolid

## API定义

```python
def cut_rsolid(solid1: Solid, solid2: Solid) -> Solid
```

*来源文件: operations.py*

## API作用

从第一个实体中减去第二个实体的重叠部分，常用于创建孔洞、凹槽等。
结果实体的体积等于solid1减去两个实体重叠部分的体积。

## API参数说明

### solid1

- **类型**: `Solid`
- **说明**: 被减实体，作为基础实体

### solid2

- **类型**: `Solid`
- **说明**: 减去的实体，将从基础实体中移除

## 返回值说明

Solid: 差集结果实体，从solid1中减去solid2的重叠部分

## 异常

- **ValueError**: 当输入实体无效或运算失败时抛出异常

## API使用例子

```python
# 在立方体中创建圆形孔
box = make_box_rsolid(4, 4, 4)
hole = make_cylinder_rsolid(1.0, 4.0)
box_with_hole = cut_rsolid(box, hole)
# 创建槽形结构
base = make_box_rsolid(6, 3, 2)
slot = make_box_rsolid(4, 1, 2, (0, 0, 1))
slotted_base = cut_rsolid(base, slot)
# 从球体中减去立方体
sphere = make_sphere_rsolid(2.0)
cube = make_box_rsolid(2, 2, 2)
carved_sphere = cut_rsolid(sphere, cube)
```
