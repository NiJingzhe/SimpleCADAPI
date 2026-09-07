# Resolved

## Class Definition

```python
class Resolved(kind: str, name: str, view: str, requested: str, resolved: str, adjust: list = field(default_factory=list), draw: dict = field(default_factory=dict), rule: str = '')
```

*Source: dxf_engine/planner.py*

## Import Surface

- drawing namespace: `from simplecadapi.dxf_engine import Resolved`

## Description

一个标注元素在纸面上的求解结果：requested(声明值) → resolved(实际位置) +
adjust(最少调整顺延记录) + draw(渲染所需的预计算几何) + rules(触发的规则)。
