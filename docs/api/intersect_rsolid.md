# intersect_rsolid

## API定义

```python
def intersect_rsolid(solid1: Solid, solid2: Solid) -> Solid
```

*来源文件: operations.py*

## API作用

计算两个实体的交集，返回只包含两个实体重叠部分的新实体。
如果两个实体不相交，可能返回空实体。交集体积小于等于任一输入实体。

## API参数说明

### solid1

- **类型**: `Solid`
- **说明**: 第一个参与运算的实体对象

### solid2

- **类型**: `Solid`
- **说明**: 第二个参与运算的实体对象

## 返回值说明

Solid: 两个实体的交集结果，只包含两个实体的重叠部分

## 异常

- **ValueError**: 当输入实体无效或运算失败时抛出异常

## API使用例子

```python
# 计算两个重叠立方体的交集
box1 = make_box_rsolid(3, 3, 3, (0, 0, 0))
box2 = make_box_rsolid(3, 3, 3, (1, 1, 0))
intersection = intersect_rsolid(box1, box2)
# 结果是一个2×2×3的立方体
# 球体和立方体的交集
sphere = make_sphere_rsolid(2.0)
cube = make_box_rsolid(3, 3, 3)
rounded_cube = intersect_rsolid(sphere, cube)
# 圆柱体和平面的交集
cylinder = make_cylinder_rsolid(1.5, 4.0)
slab = make_box_rsolid(4, 4, 2, (0, 0, 1))
partial_cylinder = intersect_rsolid(cylinder, slab)
```
