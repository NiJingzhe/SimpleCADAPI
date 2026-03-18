# geo

## API Definition

```python
def geo(field: str, default: Any = None) -> KeyFn
```

*Source: ql.py*

## Description

快捷构造 geo 元数据取值函数。

Q.select(items).order_by(Q.geo("height"))

## Parameters

### field

- **Description**: geo 字段名，如 "type"、"height"。

### default

- **Description**: 取值失败时的默认值。

## Returns

Callable[[Any], Any]: 取值函数。
