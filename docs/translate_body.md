# translate_body

## 描述
将实体沿指定向量平移，创建新的实体对象。

## 语法
```python
translate_body(body: Body, vector: Tuple[float, float, float]) -> Body
```

## 参数
- **body** (Body): 要平移的实体
- **vector** (Tuple[float, float, float]): 平移向量 (x, y, z)

## 返回值
- **Body**: 平移后的新实体

## 异常
- **ValueError**: 当输入实体无效时抛出

## 示例

### 基本平移操作
```python
from simplecadapi import *

# 创建一个立方体
cube = make_box(1.0, 1.0, 1.0)

# 沿X轴平移2单位
translated_cube = translate_body(cube, vector=(2.0, 0.0, 0.0))

# 沿多个轴平移
moved_cube = translate_body(cube, vector=(1.0, 2.0, 3.0))
```

### 复杂实体平移
```python
# 创建一个圆柱体
cylinder = make_cylinder(0.5, 2.0)

# 平移到新位置
new_cylinder = translate_body(cylinder, vector=(5.0, 5.0, 0.0))

# 导出结果
export_stl(new_cylinder, "translated_cylinder.stl")
```

### 多次平移
```python
# 创建基础形状
base_shape = make_sphere(0.5)

# 连续平移
shape1 = translate_body(base_shape, vector=(1.0, 0.0, 0.0))
shape2 = translate_body(shape1, vector=(0.0, 1.0, 0.0))
shape3 = translate_body(shape2, vector=(0.0, 0.0, 1.0))

# 合并所有形状
combined = union(union(union(base_shape, shape1), shape2), shape3)
```

## 注意事项
- 平移操作不会修改原始实体，而是创建新的实体
- 向量使用SimpleCAD坐标系 (x, y, z)
- 平移向量的单位与模型单位一致
- 可以使用负值进行反向平移

## 相关函数
- [rotate_body](rotate_body.md) - 旋转实体
- [make_linear_pattern](make_linear_pattern.md) - 线性阵列（包含平移）
- [union](union.md) - 合并多个实体
