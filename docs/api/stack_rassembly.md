# stack_rassembly

## API定义

```python
def stack_rassembly(assembly: Assembly, parts: Sequence[Union[str, PartHandle]], axis: str = 'z', gap: float = 0.0, align: Literal['center', 'start', 'end'] = 'center', justify: Literal['start', 'center', 'end', 'space-between'] = 'start', bounds: Optional[Tuple[PointAnchor, PointAnchor]] = None) -> Assembly
```

*来源文件: constraints.py*

## API作用

Type-2映射：应用 stack 布局并返回新装配对象。
