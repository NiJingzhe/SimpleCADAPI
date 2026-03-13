# or_

## API Definition

```python
def or_(*predicates: Predicate) -> Predicate
```

*Source: ql.py*

## Description

构造 OR 组合谓词。

Q.or_(Q.tag("face.top"), Q.tag("face.bottom"))

## Parameters

### *predicates

- **Description**: 任意数量谓词。

## Returns

Callable[[Any], bool]: 组合谓词。
