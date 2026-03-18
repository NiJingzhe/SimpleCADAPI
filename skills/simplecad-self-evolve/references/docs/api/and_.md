# and_

## API Definition

```python
def and_(*predicates: Predicate) -> Predicate
```

*Source: ql.py*

## Description

构造 AND 组合谓词。

Q.and_(Q.tag("face.top"), Q.tag("role.mounting_surface"))

## Parameters

### *predicates

- **Description**: 任意数量谓词。

## Returns

Callable[[Any], bool]: 组合谓词。
