# geo

## API Definition

```python
def geo(field: str, default: Any = None) -> KeyFn
```

*Source: ql.py*

## Description

Convenience builder for a `geo` metadata getter.

Q.select(items).order_by(Q.geo("height"))

## Parameters

### field

- **Description**: `geo` field name, such as `type` or `height`.

### default

- **Description**: Default value when lookup fails.

## Returns

Callable[[Any], Any]: Getter function.
