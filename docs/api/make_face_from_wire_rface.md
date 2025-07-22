# make_face_from_wire_rface

## API定义

```python
def make_face_from_wire_rface(wire: Wire, normal: Tuple[float, float, float] = (0, 0, 1)) -> Face
```

## API作用

将封闭的线轮廓转换为面对象，用于从复杂的线框轮廓创建面。输入的线必须
是封闭的，函数会检查面的法向量方向，如果与期望方向相反会发出警告。

## API参数说明

### wire

- **类型**: `Wire`
- **说明**: 输入的线对象，必须是封闭的线轮廓

### normal

- **类型**: `Tuple[float, float, float], optional`
- **说明**: 期望的面法向量 (x, y, z)， 用于确定面的方向，默认为 (0, 0, 1)

### 返回值

Face: 创建的面对象，由输入的线轮廓围成的面

## 异常

- **ValueError**: 当输入的线对象无效、不封闭或创建面失败时抛出异常
