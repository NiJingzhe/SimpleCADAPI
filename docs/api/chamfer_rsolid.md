# chamfer_rsolid

## API定义

```python
def chamfer_rsolid(solid: Solid, edges: List[Edge], distance: float) -> Solid
```

## API作用

对实体的指定边进行倒角处理，创建斜面过渡。与圆角不同，倒角创建的是
平面过渡而不是圆弧过渡。常用于机械零件的边缘处理，便于装配和安全。

## API参数说明

### solid

- **类型**: `Solid`
- **说明**: 要进行倒角操作的实体对象

### edges

- **类型**: `List[Edge]`
- **说明**: 要进行倒角的边列表，通常从实体获取

### distance

- **类型**: `float`
- **说明**: 倒角距离，必须为正数，定义从边缘向内的倒角深度

### 返回值

Solid: 倒角后的实体对象

## 异常

- **ValueError**: 当倒角距离小于等于0或倒角操作失败时抛出异常
