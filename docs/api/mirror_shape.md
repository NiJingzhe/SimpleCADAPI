# mirror_shape

## API定义

```python
def mirror_shape(shape: AnyShape, plane_origin: Tuple[float, float, float], plane_normal: Tuple[float, float, float]) -> AnyShape
```

*来源文件: operations.py*

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

## 返回值说明

AnyShape: 镜像后的几何体，类型与输入相同

## 异常

- **ValueError**: 当几何体或镜像平面参数无效时抛出异常

## API使用例子

```python
# 沿YZ平面镜像立方体
box = make_box_rsolid(2, 2, 2, (1, 0, 0))
mirrored_box = mirror_shape(box, (0, 0, 0), (1, 0, 0))
# 沿XY平面镜像圆柱体
cylinder = make_cylinder_rsolid(1.0, 3.0, (0, 0, 1))
mirrored_cyl = mirror_shape(cylinder, (0, 0, 0), (0, 0, 1))
# 沿任意平面镜像
sphere = make_sphere_rsolid(1.5, (2, 2, 0))
mirrored_sphere = mirror_shape(sphere, (1, 1, 0), (1, 1, 0))
```
