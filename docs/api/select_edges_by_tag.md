# select_edges_by_tag

## API Definition

```python
def select_edges_by_tag(
    shape: Union[Face, Solid],
    tag: str,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[Edge]
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import select_edges_by_tag`

## Description

Select edges by an exact normalized tag in the requested semantic scope.
`effective` does not include lineage; request `scope="lineage"` explicitly when
selection depends on complete topology-history evidence.
