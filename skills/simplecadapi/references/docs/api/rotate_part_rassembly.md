# rotate_part_rassembly

## API Definition

```python
def rotate_part_rassembly(assembly: Assembly, part: Union[str, PartHandle], angle_deg: float, axis: AxisLike = 'z', origin: Vec3Like = (0.0, 0.0, 0.0), frame: Literal['world', 'local'] = 'world') -> Assembly
```

*Source: constraints.py*

## Description

Type-2 mapping: rotate a part and return a new assembly.
