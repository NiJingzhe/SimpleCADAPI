# select

## API Definition

```python
def select(items: Iterable[Any]) -> Query
```

*Source: ql.py*

## Description

Create a query object.

Q.select(items).where(Q.tag("face.top")).first()

## Parameters

### items

- **Description**: Any iterable.

## Returns

Query: Query object.
