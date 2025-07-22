# make_line_redge

## API定义

```python
def make_line_redge(start: Tuple[float, float, float], end: Tuple[float, float, float]) -> Edge
```

## API作用

创建两点之间的直线段，是构建复杂几何形状的基础元素。可用于构造线框、
创建草图轮廓、定义路径等。支持当前坐标系变换。

## API参数说明

### start

- **类型**: `Tuple[float, float, float]`
- **说明**: 起始点坐标 (x, y, z)，定义线段的起点

### end

- **类型**: `Tuple[float, float, float]`
- **说明**: 结束点坐标 (x, y, z)，定义线段的终点

### 返回值

Edge: 创建的边对象，表示连接两点的直线段

## 异常

- **ValueError**: 当坐标无效或起始点与结束点重合时抛出异常

## API使用例子

```python
...     elevated_line = make_line_redge((0, 0, 0), (2, 2, 0))
```
