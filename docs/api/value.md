# value

## API Definition

```python
def value(path: str, default: Any = None) -> KeyFn
```

*Source: ql.py*

## Description

Build a value getter for sorting or projection.

Q.select(items).order_by(Q.value("geo.height"))

## Parameters

### path

- **Description**: Metadata path, for example `geo.height`.

### default

- **Description**: Default value when lookup fails.

## Returns

Callable[[Any], Any]: Getter function.

## Examples

```python
key = Q.value("geo.height", 0.0)
height = key(obj)
```
