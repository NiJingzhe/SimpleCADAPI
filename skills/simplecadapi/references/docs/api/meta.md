# meta

## API Definition

```python
def meta(path: str, op: str, value_: Any) -> SerializablePredicate
```

*Source: ql.py*

## Description

Build a metadata comparison predicate for QL filtering.

## Parameters

### path

- **Description**: Dot-separated metadata path.

### op

- **Description**: Comparison operator such as `==`, `!=`, `>`, `>=`, `<`, or `<=`.

### value_

- **Description**: Comparison value.

## Returns

Serializable predicate that compares metadata values.
