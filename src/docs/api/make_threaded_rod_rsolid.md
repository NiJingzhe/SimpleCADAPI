# make_threaded_rod_rsolid

## API定义

```python
def make_threaded_rod_rsolid(thread_diameter = 8.0, thread_length = 20.0, total_length = 30.0, thread_pitch = 1.25, thread_start_position = 0.0, chamfer_size = 0.5) -> Solid
```

*来源文件: evolve.py*

## API作用

创建带螺纹的螺杆，支持可调节的杆子长度、螺纹范围和螺距
螺纹杆直径：螺纹杆直径（螺纹大径）
螺纹杆长度：螺纹部分长度
螺杆总长度：螺杆总长度
螺纹螺距：螺纹螺距
螺纹起始位置：螺纹起始位置（从螺杆底部算起）
螺杆末端倒角：螺杆末端倒角尺寸

## API参数说明

### thread_diameter

- **类型**: `float`
- **说明**: 螺纹杆直径（螺纹大径）

### thread_length

- **类型**: `float`
- **说明**: 螺纹部分长度

### total_length

- **类型**: `float`
- **说明**: 螺杆总长度

### thread_pitch

- **类型**: `float`
- **说明**: 螺纹螺距

### thread_start_position

- **类型**: `float`
- **说明**: 螺纹起始位置（从螺杆底部算起）

### chamfer_size

- **类型**: `float`
- **说明**: 螺杆末端倒角尺寸

## 返回值说明

Solid: 创建的带螺纹螺杆

## 异常

- **ValueError**: 如果螺杆参数无效（如直径小于等于0、长度不合理等）
- **ValueError**: 如果螺纹参数无效（如螺距小于等于0、螺纹长度大于总长度等）
- **ValueError**: 如果螺纹起始位置超出螺杆范围

## API使用例子

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
