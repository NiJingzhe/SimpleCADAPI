# constrain_distance_rassembly

## API定义

```python
def constrain_distance_rassembly(assembly: Assembly, reference: PointAnchor, moving: PointAnchor, distance: float, fallback_axis: AxisLike = 'x') -> Assembly
```

*来源文件: constraints.py*

## API作用

Type-2映射：添加点距约束并返回新装配对象。
