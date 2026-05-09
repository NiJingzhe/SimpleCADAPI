# tag

## API Definition

```python
def tag(pattern: str) -> SerializablePredicate
```

*Source: ql.py*

## Description

Build a tag predicate for QL filtering.

## Parameters

### pattern

- **Description**: Exact tag string or a trailing `*` prefix match.

## Returns

Serializable predicate that can be used in `Query.where(...)`.
