# not_

## API Definition

```python
def not_(predicate: Predicate) -> Predicate
```

*Source: ql.py*

## Description

构造 NOT 谓词。

Q.not_(Q.tag("state.*"))

## Parameters

### predicate

- **Description**: 单个谓词。

## Returns

Callable[[Any], bool]: 取反谓词。
