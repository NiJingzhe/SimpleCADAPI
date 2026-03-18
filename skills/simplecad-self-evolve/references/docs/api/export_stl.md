# export_stl

## API Definition

```python
def export_stl(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None
```

*Source: operations.py*

## Description

导出为STL格式

## Parameters

### shapes

- **Description**: 要导出的几何体或几何体列表

### filename

- **Description**: 输出文件名

## Raises

- **ValueError**: 当导出失败时
