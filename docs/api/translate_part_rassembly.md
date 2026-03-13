# translate_part_rassembly

## API Definition

```python
def translate_part_rassembly(assembly: Assembly, part: Union[str, PartHandle], vector: Vec3Like, frame: Literal['world', 'local'] = 'world') -> Assembly
```

*Source: constraints.py*

## Description

Type-2映射：平移零件并返回新装配对象。
