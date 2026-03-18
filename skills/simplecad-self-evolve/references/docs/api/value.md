# value

## API Definition

```python
def value(path: str, default: Any = None) -> KeyFn
```

*Source: ql.py*

## Description

构造取值函数，用于排序或投影。

Q.select(items).order_by(Q.value("geo.height"))

## Parameters

### path

- **Description**: 元数据路径，例如 "geo.height"。

### default

- **Description**: 取值失败时的默认值。

## Returns

Callable[[Any], Any]: 取值函数。

## Examples

```python
key = Q.value("geo.height", 0.0)
height = key(obj)
```
