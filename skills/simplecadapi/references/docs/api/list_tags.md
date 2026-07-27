# list_tags

## API Definition

```python
def list_tags(
    shape: AnyShape,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[str]
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import list_tags`

## Description

Return shape tags in deterministic sorted order for one semantic scope.

- `local`: bindings attached directly to the entity.
- `inherited`: bindings visible through explicit downward topology propagation.
- `effective`: local plus inherited bindings. Lineage is not included.
- `lineage`: bindings visible through complete, policy-allowed topology history.

Lineage queries fail with a semantic capability error when complete topology
history is unavailable; they do not guess from geometry or enumeration order.
