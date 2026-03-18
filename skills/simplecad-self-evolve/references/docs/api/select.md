# select

## API Definition

```python
def select(items: Iterable[Any]) -> Query
```

*Source: ql.py*

## Description

创建查询对象。

Q.select(items).where(Q.tag("face.top")).first()

## Parameters

### items

- **Description**: 任意可迭代对象。

## Returns

Query: 查询对象。
