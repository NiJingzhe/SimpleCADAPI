# make_assembly_rassembly

## API Definition

```python
def make_assembly_rassembly(parts: Sequence[Tuple[str, Solid]], name: str = 'assembly', parents: Optional[Dict[str, str]] = None, local_transforms: Optional[Dict[str, Union[np.ndarray, Sequence[Sequence[float]]]]] = None) -> Assembly
```

*Source: constraints.py*

## Description

Type-1映射：从参数描述提升到装配对象。
