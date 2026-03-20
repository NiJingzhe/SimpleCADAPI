# not_

## API Definition

```python
def not_(predicate: Predicate) -> Predicate
```

*Source: ql.py*

## Description

Build a NOT predicate.

Q.not_(Q.tag("state.*"))

## Parameters

### predicate

- **Description**: A single predicate.

## Returns

Callable[[Any], bool]: Negated predicate.
