# make_segment_rwire

## API定义

```python
def make_segment_rwire(start: Tuple[float, float, float], end: Tuple[float, float, float]) -> Wire
```

*来源文件: operations.py*

## API作用

创建包含单个线段的线对象，用于构建更复杂的线框结构。与make_segment_redge
不同，此函数返回的是线对象，可以与其他线对象连接形成复杂路径。

## API参数说明

### start

- **类型**: `Tuple[float, float, float]`
- **说明**: 起始点坐标 (x, y, z)，定义线段的起点

### end

- **类型**: `Tuple[float, float, float]`
- **说明**: 结束点坐标 (x, y, z)，定义线段的终点

## 返回值说明

Wire: 创建的线对象，包含一个连接两点的直线段

## 异常

- **ValueError**: 当坐标无效或创建线对象失败时抛出异常

## API使用例子

```python
# 创建基本线段线
wire = make_segment_rwire((0, 0, 0), (3, 0, 0))
# 创建斜线段
diagonal_wire = make_segment_rwire((0, 0, 0), (2, 2, 0))
```
