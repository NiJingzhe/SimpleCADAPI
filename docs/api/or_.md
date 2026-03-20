# or_

## API Definition

```python
def or_(*predicates: Predicate) -> Predicate
```

*Source: ql.py*

## Description

Build an OR-composed predicate.

Q.or_(Q.tag("face.top"), Q.tag("face.bottom"))

## Parameters

### *predicates

- **Description**: Any number of predicates.

## Returns

Callable[[Any], bool]: Combined predicate.
