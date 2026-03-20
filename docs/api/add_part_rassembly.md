# add_part_rassembly

## API Definition

```python
def add_part_rassembly(assembly: Assembly, name: str, solid: Solid, parent: Optional[Union[str, PartHandle]] = None, local_transform: Optional[Union[np.ndarray, Sequence[Sequence[float]]]] = None) -> Assembly
```

*Source: constraints.py*

## Description

Type-2 mapping: add a part in assembly space and return a new assembly.
