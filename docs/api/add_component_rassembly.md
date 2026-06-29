# add_component_rassembly

## API Definition

```python
def add_component_rassembly(assembly: Assembly, item: Union[Part, Assembly], component_id: str, placement: Placement, name: Optional[str] = None) -> Assembly
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import add_component_rassembly`

## Description

Add a placed Part or subassembly component instance to an Assembly.
