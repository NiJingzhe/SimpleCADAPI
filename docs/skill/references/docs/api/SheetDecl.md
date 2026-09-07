# SheetDecl

## Class Definition

```python
class SheetDecl(title: str, dwg_no: str, scale: float, front: str, anchor: tuple, views: list, datums: list = field(default_factory=list), dims: list = field(default_factory=list), centers: list = field(default_factory=list), leaders: list = field(default_factory=list), notes: list = field(default_factory=list), params: dict = field(default_factory=dict), material: str = 'PLA-CF / PAHT', notes_zone: tuple = (25.0, 5.0, 232.0, 90.0), diag_png: str = '')
```

*Source: dxf_engine/model.py*

## Import Surface

- drawing namespace: `from simplecadapi.dxf_engine import SheetDecl`

## Description

一张图纸的完整声明：图幅信息 + 视图 + 基准 + 尺寸 + 中心线 + 引出说明 + 参数表。

调用方只声明"要表达什么"，不指定任何纸面坐标；布局与标注位置由
SheetPlan.solve() 求解。front/anchor 定义主视图锚定，其余视图经
ViewDecl.align 相对主视图对正（第一角投影，长对正/高平齐）。
