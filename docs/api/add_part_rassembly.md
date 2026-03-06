# add_part_rassembly

## API定义

```python
def add_part_rassembly(assembly: Assembly, name: str, solid: Solid, parent: Optional[Union[str, PartHandle]] = None, local_transform: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None) -> Assembly
```

*来源文件: constraints.py*

## API作用

Type-2映射：在装配空间中新增零件并返回新装配对象。
