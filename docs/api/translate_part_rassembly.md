# translate_part_rassembly

## API定义

```python
def translate_part_rassembly(assembly: Assembly, part: Union[str, PartHandle], vector: Vec3Like, frame: Literal['world', 'local'] = 'world') -> Assembly
```

*来源文件: constraints.py*

## API作用

Type-2映射：平移零件并返回新装配对象。
