# explain_tag

## API Definition

```python
def explain_tag(shape: AnyShape, tag: str, scope: str | TagScope = TagScope.EFFECTIVE) -> List[Dict[str, Any]]
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import explain_tag`

## Description

Explain every visible binding that produces a tag token.
