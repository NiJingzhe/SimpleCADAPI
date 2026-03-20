# and_

## API Definition

```python
def and_(*predicates: Predicate) -> Predicate
```

*Source: ql.py*

## Description

Build an AND-composed predicate.

Q.and_(Q.tag("face.top"), Q.tag("role.mounting_surface"))

## Parameters

### *predicates

- **Description**: Any number of predicates.

## Returns

Callable[[Any], bool]: Combined predicate.
