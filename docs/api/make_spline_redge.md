# make_spline_redge

## API定义

```python
def make_spline_redge(points: List[Tuple[float, float, float]], tangents: Optional[List[Tuple[float, float, float]]] = None) -> Edge
```

## API作用

创建平滑的样条曲线边，用于构建复杂的曲线路径。样条曲线会平滑地通过
所有控制点，可选择性地指定每个点的切线方向来控制曲线的形状。

## API参数说明

### points

- **类型**: `List[Tuple[float, float, float]]`
- **说明**: 控制点坐标列表 [(x, y, z), ...]， 至少需要2个点，点的顺序决定样条曲线的走向

### tangents

- **类型**: `Optional[List[Tuple[float, float, float]]], optional`
- **说明**:  可选的切线向量列表 [(x, y, z), ...]，如果提供则数量必须与控制点一致

### 返回值

Edge: 创建的边对象，表示通过控制点的平滑样条曲线

## 异常

- **ValueError**: 当控制点少于2个或切线向量数量不匹配时抛出异常
