# tag

## API Definition

```python
def tag(pattern: str) -> Predicate
```

*Source: ql.py*

## Description

Build a tag-based predicate.

`Q.tag("face.top")` or `Q.tag("role.*")`.

## Parameters

### pattern

- **Description**: Tag matching pattern. Supports a trailing `*` wildcard.

## Returns

Callable[[Any], bool]: Predicate function.

## Raises

- **TypeError**: If pattern is not a string.
- **ValueError**: If the wildcard position is invalid.

## Examples

```python
pred = Q.tag("role.*")
matched = pred(obj)
```
