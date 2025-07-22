# make_spline_rwire

## API定义

```python
def make_spline_rwire(points: List[Tuple[float, float, float]], tangents: Optional[List[Tuple[float, float, float]]] = None, closed: bool = False) -> Wire
```

## API作用

创建样条曲线线对象，与make_spline_redge功能相同但返回线对象。
可以设置为闭合样条曲线，适用于构建复杂的封闭轮廓。

## API参数说明

### points

- **类型**: `List[Tuple[float, float, float]]`
- **说明**: 控制点坐标列表 [(x, y, z), ...]， 至少需要2个点，点的顺序决定样条曲线的走向

### tangents

- **类型**: `Optional[List[Tuple[float, float, float]]], optional`
- **说明**:  可选的切线向量列表 [(x, y, z), ...]，如果提供则数量必须与控制点一致

### closed

- **类型**: `bool, optional`
- **说明**: 是否创建闭合的样条曲线，默认为False

### 返回值

Wire: 创建的线对象，包含一个样条曲线

## 异常

- **ValueError**: 当控制点少于2个或切线向量数量不匹配时抛出异常
