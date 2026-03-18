# tag

## API Definition

```python
def tag(pattern: str) -> Predicate
```

*Source: ql.py*

## Description

构造基于标签的谓词。

Q.tag("face.top") 或 Q.tag("role.*")。

## Parameters

### pattern

- **Description**: 标签匹配模式，支持后缀通配符 "*"。

## Returns

Callable[[Any], bool]: 谓词函数。

## Raises

- **TypeError**: pattern 不是字符串。
- **ValueError**: 通配符位置不合法。

## Examples

```python
pred = Q.tag("role.*")
matched = pred(obj)
```
