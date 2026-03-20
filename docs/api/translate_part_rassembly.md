# translate_part_rassembly

## API Definition

```python
def translate_part_rassembly(assembly: Assembly, part: Union[str, PartHandle], vector: Vec3Like, frame: Literal['world', 'local'] = 'world') -> Assembly
```

*Source: constraints.py*

## Description

Type-2 mapping: translate a part and return a new assembly.
