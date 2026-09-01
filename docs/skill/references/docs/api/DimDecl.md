# DimDecl

## Class Definition

```python
class DimDecl(kind: str, view: str, semantic: str, caption: str, value: float = None, p1: tuple = None, p2: tuple = None, center: tuple = None, radius: float = None, at: float = None, datum: str = None, side: str = None, row: int = 0, out: float = 8.0, dec: int = 0, prefix: str = '', covers: list = field(default_factory=list), name: str = '')
```

*Source: dxf_engine/model.py*

## Import Surface

- drawing namespace: `from simplecadapi.dxf_engine import DimDecl`

## Description

一条尺寸声明。kind=定位(position)尺寸必须在 datum 里引用已声明基准。
