# linear_pattern_rsolidlist

## API定义

```python
def linear_pattern_rsolidlist(shape: AnyShape, direction: Tuple[float, float, float], count: int, spacing: float) -> List[Solid]
```

*来源文件: operations.py*

## API作用

沿指定方向创建几何体的线性阵列，生成指定数量的等间距排列对象。
常用于创建重复结构，如齿轮齿、栅栏、螺栓阵列等。

## API参数说明

### shape

- **类型**: `AnyShape`
- **说明**: 要阵列的几何体，可以是任意类型的几何对象

### direction

- **类型**: `Tuple[float, float, float]`
- **说明**: 阵列方向向量 (x, y, z)， 定义阵列的方向，会被标准化处理

### count

- **类型**: `int`
- **说明**: 阵列数量，必须为正整数，包括原始对象

### spacing

- **类型**: `float`
- **说明**: 阵列间距，必须为正数，定义相邻对象间的距离

## 返回值说明

List[Solid]: 阵列后的几何体列表，包含原始对象和所有复制的对象

## 异常

- **ValueError**: 当阵列数量小于等于0或间距小于等于0时抛出异常

## API使用例子

```python
# 创建立方体的线性阵列
box = make_box_rsolid(1, 1, 1)
boxes = linear_pattern_rsolidlist(box, (2, 0, 0), 5, 2.0)
# 创建5个立方体，沿X轴方向间距2.0
# 创建圆柱体的对角线阵列
cylinder = make_cylinder_rsolid(0.5, 2.0)
cylinders = linear_pattern_rsolidlist(cylinder, (1, 1, 0), 4, 1.5)
# 创建复杂几何体的阵列
complex_shape = union_rsolid(box, cylinder)
array = linear_pattern_rsolidlist(complex_shape, (0, 3, 0), 3, 3.0)
```
