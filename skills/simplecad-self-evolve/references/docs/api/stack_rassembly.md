# stack_rassembly

## API Definition

```python
def stack_rassembly(assembly: Assembly, parts: Sequence[Union[str, PartHandle]], axis: str = 'z', gap: float = 0.0, align: Literal['center', 'start', 'end'] = 'center', justify: Literal['start', 'center', 'end', 'space-between'] = 'start', bounds: Optional[Tuple[PointAnchor, PointAnchor]] = None) -> Assembly
```

*Source: constraints.py*

## Description

Type-2 mapping: apply a stack layout and return a new assembly.
