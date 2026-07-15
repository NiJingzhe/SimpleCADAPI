# select_faces_by_tag

## API Definition

```python
def select_faces_by_tag(
    solid: Solid,
    tag: str,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[Face]
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import select_faces_by_tag`

## Description

Select faces by an exact normalized tag in the requested semantic scope.
`effective` does not include lineage; request `scope="lineage"` explicitly when
selection depends on complete topology-history evidence.
