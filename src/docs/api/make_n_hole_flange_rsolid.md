# make_n_hole_flange_rsolid

## API定义

```python
def make_n_hole_flange_rsolid(flange_outer_diameter = 120.0, flange_inner_diameter = 60.0, flange_thickness = 15.0, boss_outer_diameter = 80.0, boss_height = 5.0, hole_diameter = 8.0, hole_circle_diameter = 100.0, hole_count = 8, chamfer_size = 1.0) -> Solid
```

*来源文件: evolve.py*

## API作用

创建n孔法兰，包含中心凸起圆环和倒角，最终法兰的底面中心在原点(0,0,0)
体积等于法兰外径×法兰厚度+凸起圆环体积-连接孔体积-倒角体积
法兰外径×法兰厚度：法兰主体体积
凸起圆环体积：凸起圆环体积
连接孔体积：连接孔体积
倒角体积：倒角体积

## API参数说明

### flange_outer_diameter

- **类型**: `float`
- **说明**: 法兰外径

### flange_inner_diameter

- **类型**: `float`
- **说明**: 法兰内径

### flange_thickness

- **类型**: `float`
- **说明**: 法兰厚度

### boss_outer_diameter

- **类型**: `float`
- **说明**: 凸起圆环外径

### boss_height

- **类型**: `float`
- **说明**: 凸起圆环高度

### hole_diameter

- **类型**: `float`
- **说明**: 连接孔直径

### hole_circle_diameter

- **类型**: `float`
- **说明**: 连接孔分布圆直径

### hole_count

- **类型**: `int`
- **说明**: 连接孔数量

### chamfer_size

- **类型**: `float`
- **说明**: 倒角尺寸

## 返回值说明

Solid: 创建的n孔法兰

## 异常

- **ValueError**: 如果在创建法兰主体、切割内孔、或后续几何操作过程中发生错误（如几何体重叠、尺寸不合理等），会抛出该异常。
- **TypeError**: 如果传入的参数类型不正确（如应为float却传入了str等），会抛出该异常。
- **ValueError**: 如果参数值不在合理范围（如直径为负数、孔数量小于1、内径大于外径等），会抛出该异常。

## API使用例子

```python
flange = make_n_hole_flange_rsolid(
flange_outer_diameter=120.0,
flange_inner_diameter=60.0,
flange_thickness=15.0,
boss_outer_diameter=80.0,
boss_height=5.0,
hole_diameter=8.0,
hole_circle_diameter=100.0,
hole_count=8,
chamfer_size=1.0
)
export_stl(flange, "flange.stl")
```
