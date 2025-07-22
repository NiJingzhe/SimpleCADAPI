# make_angle_arc_rwire

## API定义

```python
def make_angle_arc_rwire(center: Tuple[float, float, float], radius: float, start_angle: float, end_angle: float, normal: Tuple[float, float, float] = (0, 0, 1)) -> Wire
```

## API作用

通过指定中心点、半径和角度范围创建圆弧线。
角度采用度数制，0度对应X轴正方向，逆时针为正角度。
可以创建任意角度范围的圆弧线。

## API参数说明

### center

- **说明**: 圆心坐标

### radius

- **说明**: 半径

### start_angle

- **说明**: 起始角度（弧度）

### end_angle

- **说明**: 结束角度（弧度）

### normal

- **说明**: 法向量

### 返回值

Wire: 线对象，表示通过角度创建的圆弧线

## 异常

- **ValueError**: 当半径小于等于0或其他参数无效时
