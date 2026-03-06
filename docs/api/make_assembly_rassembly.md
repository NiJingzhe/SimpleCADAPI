# make_assembly_rassembly

## API定义

```python
def make_assembly_rassembly(parts: Sequence[Tuple[str, Solid]], name: str = 'assembly', parents: Optional[Dict[str, str]] = None, local_transforms: Optional[Dict[str, Union[np.ndarray, Sequence[Sequence[float]]]]] = None) -> Assembly
```

*来源文件: constraints.py*

## API作用

Type-1映射：从参数描述提升到装配对象。
