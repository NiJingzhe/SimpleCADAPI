# make_naca_propeller_blade_rsolid

## API Definition

```python
def make_naca_propeller_blade_rsolid(blade_length = 5.0, root_chord = 1.5, tip_chord = 0.3, total_twist_angle = 45.0, num_sections = 7, t_c = 0.16) -> Solid
```

*Source: evolve.py*

## Description

创建单个螺旋桨叶片模型, 默认使用NACA0016翼型，扭转45度，7个截面，厚度比16%
最终桨叶的根部在原点，桨叶沿着Z轴方向延伸

创建单个螺旋桨叶片模型, 默认使用NACA0016翼型，扭转45度，7个截面，厚度比16%
厚度比：翼型厚度比（0.0到1.0）, NACA0016为0.16

## Parameters

### blade_length

- **Type**: `float`
- **Description**: 桨叶径向长度

### root_chord

- **Type**: `float`
- **Description**: 桨叶根部弦长

### tip_chord

- **Type**: `float`
- **Description**: 桨叶叶尖弦长

### total_twist_angle

- **Type**: `float`
- **Description**: 桨叶从根部到叶尖的总扭转角度（度）

### num_sections

- **Type**: `int`
- **Description**: 沿径向生成的截面数量

### t_c

- **Type**: `float`
- **Description**: 翼型厚度比（0.0到1.0）, NACA0016为0.16

## Returns

Solid: 螺旋桨叶片实体

## Raises

- **ValueError**: 如果翼型截面生成失败，可能是NACA翼型计算或几何变换失败
- **ValueError**: 如果截面数量不足，需要至少2个截面
- **ValueError**: 如果放样结果不是有效的Solid对象
- **ValueError**: 如果翼型厚度比超出有效范围（0.0到1.0）

## Examples

```python
# 创建一个扭转45度，7个截面，厚度比16%的螺旋桨叶片
blade = make_naca_propeller_blade_rsolid(
    blade_length=5.0,
    root_chord=1.5,
    tip_chord=0.3,
    total_twist_angle=45.0,
    num_sections=7,
    t_c=0.16,
)
```
