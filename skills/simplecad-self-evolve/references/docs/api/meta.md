# meta

## API Definition

```python
def meta(path: str, op: str, value: Any) -> Predicate
```

*Source: ql.py*

## Description

构造基于元数据的谓词。

Q.meta("geo.type", "==", "box")

## Parameters

### path

- **Description**: 元数据路径，例如 "geo.type"。

### op

- **Description**: 比较操作符，支持 == != > >= < <= 。

### value

- **Description**: 比较目标值。

## Returns

Callable[[Any], bool]: 谓词函数。

## Raises

- **TypeError**: op 不是字符串。
- **ValueError**: 操作符不支持。

## Examples

```python
pred = Q.meta("geo.size.x", ">", 1.0)
matched = pred(obj)
```
