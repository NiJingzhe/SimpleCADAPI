# ViewDecl

## Class Definition

```python
class ViewDecl(name: str, shape: object, n: tuple, xd: tuple, align: dict = field(default_factory=dict), anchor: tuple | None = None)
```

*Source: dxf_engine/model.py*

## Import Surface

- drawing namespace: `from simplecadapi.dxf_engine import ViewDecl`

## Description

HLR 投影视图。n=观察方向, xd=投影面内屏幕右方向; align 定义布局约束。
