# explain_tag

## API Definition

```python
def explain_tag(
    shape: AnyShape,
    tag: str,
    scope: str | TagScope = TagScope.EFFECTIVE,
) -> List[Dict[str, Any]]
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import explain_tag`

## Description

Return every visible canonical binding that produces `tag` in the requested
scope. Explanations preserve binding identity, producer, attachment, evidence,
and policy-allowed lineage witnesses, so equal tag tokens from different
producers remain distinguishable.

As with `list_tags(...)`, `effective` excludes lineage. A lineage explanation
requires complete topology-history coverage.
