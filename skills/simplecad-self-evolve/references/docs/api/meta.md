# meta

## API Definition

```python
def meta(path: str, op: str, value: Any) -> Predicate
```

*Source: ql.py*

## Description

Build a metadata-based predicate.

Q.meta("geo.type", "==", "box")

## Parameters

### path

- **Description**: Metadata path, for example `geo.type`.

### op

- **Description**: Comparison operator. Supports `==`, `!=`, `>`, `>=`, `<`, and `<=`.

### value

- **Description**: Comparison target value.

## Returns

Callable[[Any], bool]: Predicate function.

## Raises

- **TypeError**: If op is not a string.
- **ValueError**: If the operator is unsupported.

## Examples

```python
pred = Q.meta("geo.size.x", ">", 1.0)
matched = pred(obj)
```
