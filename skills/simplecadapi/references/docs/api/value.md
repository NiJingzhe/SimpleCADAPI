# value

## API Definition

```python
def value(path: str, default: Any = None) -> SerializableKey
```

*Source: ql.py*

## Description

Build a value key extractor for ordering and projection in QL.

## Parameters

### path

- **Description**: Property or metadata path to resolve.

### default

- **Description**: Fallback value when the path is missing.

## Returns

Serializable key function for `Query.order_by(...)`.
