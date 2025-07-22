# fillet_rsolid

## API定义

```python
def fillet_rsolid(solid: Solid, edges: List[Edge], radius: float) -> Solid
```

## API作用

对实体的指定边进行圆角处理，创建平滑的过渡面。常用于消除尖锐边缘，
改善外观和减少应力集中。圆角半径不能太大，否则可能导致几何冲突。

## API参数说明

### solid

- **类型**: `Solid`
- **说明**: 要进行圆角操作的实体对象

### edges

- **类型**: `List[Edge]`
- **说明**: 要进行圆角的边列表，通常从实体获取

### radius

- **类型**: `float`
- **说明**: 圆角半径，必须为正数，不能大于相邻面的最小尺寸

### 返回值

Solid: 圆角后的实体对象

## 异常

- **ValueError**: 当圆角半径小于等于0或圆角操作失败时抛出异常
