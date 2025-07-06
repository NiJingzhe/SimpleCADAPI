# export_stl

## API定义

```python
def export_stl(shapes: Union[AnyShape, Sequence[AnyShape]], filename: str) -> None
```

## API参数说明

### shapes

- **说明**: 要导出的几何体或几何体列表

### filename

- **说明**: 输出文件名

## 异常

- **ValueError**: 当导出失败时
