# mirror_shape

## API定义

```python
def mirror_shape(shape: AnyShape, plane_origin: Tuple[float, float, float], plane_normal: Tuple[float, float, float]) -> AnyShape
```

## API作用

将几何体沿指定平面进行镜像复制，创建对称的几何结构。
镜像平面由一个点和法向量定义，几何体在平面另一侧生成对称副本。

## API参数说明

### shape

- **类型**: `AnyShape`
- **说明**: 要镜像的几何体，可以是任意类型的几何对象

### plane_origin

- **类型**: `Tuple[float, float, float]`
- **说明**: 镜像平面上的一个点坐标 (x, y, z)， 定义镜像平面的位置

### plane_normal

- **类型**: `Tuple[float, float, float]`
- **说明**: 镜像平面的法向量 (x, y, z)， 定义镜像平面的方向，会被标准化处理

### 返回值

AnyShape: 镜像后的几何体，类型与输入相同

## 异常

- **ValueError**: 当几何体或镜像平面参数无效时抛出异常
