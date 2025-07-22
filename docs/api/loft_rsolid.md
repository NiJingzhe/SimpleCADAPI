# loft_rsolid

## API定义

```python
def loft_rsolid(profiles: List[Wire], ruled: bool = False) -> Solid
```

## API作用

通过多个二维轮廓创建三维实体，轮廓间通过放样面连接。
常用于创建复杂的过渡形状，如飞机机翼、船体等变截面结构。

## API参数说明

### profiles

- **类型**: `List[Wire]`
- **说明**: 轮廓线列表，至少需要2个轮廓， 轮廓按顺序连接，第一个为起始轮廓，最后一个为结束轮廓

### ruled

- **类型**: `bool, optional`
- **说明**: 是否为直纹面，默认为False。 True表示轮廓间用直线连接，False表示用平滑曲面连接

### 返回值

Solid: 放样后的实体对象

## 异常

- **ValueError**: 当轮廓少于2个或放样操作失败时抛出异常
