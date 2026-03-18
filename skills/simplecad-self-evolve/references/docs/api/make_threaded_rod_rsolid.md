# make_threaded_rod_rsolid

## API Definition

```python
def make_threaded_rod_rsolid(thread_diameter = 8.0, thread_length = 20.0, total_length = 30.0, thread_pitch = 1.25, thread_start_position = 0.0, chamfer_size = 0.5) -> Solid
```

*Source: evolve.py*

## Description

创建带螺纹的螺杆，支持可调节的杆子长度、螺纹范围和螺距。
注意，创建的螺杆顶部中心在原点，向Z轴负方向延伸。

创建带螺纹的螺杆，支持可调节的杆子长度、螺纹范围和螺距
螺纹杆直径：螺纹杆直径（螺纹大径）
螺纹杆长度：螺纹部分长度
螺杆总长度：螺杆总长度
螺纹螺距：螺纹螺距
螺纹起始位置：螺纹起始位置（从螺杆底部算起）
螺杆末端倒角：螺杆末端倒角尺寸

## Parameters

### thread_diameter

- **Type**: `float`
- **Description**: 螺纹杆直径（螺纹大径）

### thread_length

- **Type**: `float`
- **Description**: 螺纹部分长度

### total_length

- **Type**: `float`
- **Description**: 螺杆总长度

### thread_pitch

- **Type**: `float`
- **Description**: 螺纹螺距

### thread_start_position

- **Type**: `float`
- **Description**: 螺纹起始位置（从螺杆底部算起）

### chamfer_size

- **Type**: `float`
- **Description**: 螺杆末端倒角尺寸

## Returns

Solid: 创建的带螺纹螺杆

## Raises

- **ValueError**: 如果螺杆参数无效（如直径小于等于0、长度不合理等）
- **ValueError**: 如果螺纹参数无效（如螺距小于等于0、螺纹长度大于总长度等）
- **ValueError**: 如果螺纹起始位置超出螺杆范围

## Examples

```python
# 创建标准M8螺杆
rod = make_threaded_rod_rsolid(
    thread_diameter=8.0,
    thread_length=20.0,
    total_length=30.0,
    thread_pitch=1.25,
    thread_start_position=0.0,
    chamfer_size=0.5
)
export_stl(rod, "threaded_rod.stl")
```
