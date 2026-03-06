# rotate_part_rassembly

## API定义

```python
def rotate_part_rassembly(assembly: Assembly, part: Union[str, PartHandle], angle_deg: float, axis: AxisLike = 'z', origin: Vec3Like = (0.0, 0.0, 0.0), frame: Literal['world', 'local'] = 'world') -> Assembly
```

*来源文件: constraints.py*

## API作用

Type-2映射：旋转零件并返回新装配对象。
