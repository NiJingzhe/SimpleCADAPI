# SheetPlan

## Class Definition

```python
class SheetPlan(decl: SheetDecl)
```

*Source: dxf_engine/planner.py*

## Import Surface

- drawing namespace: `from simplecadapi.dxf_engine import SheetPlan`

## Description

标注方案求解器：SheetDecl → solve() → resolved/accepted/report() → render()。

求解流程：视图布局(第一角投影、align 对正) → 基准安放 → 线性尺寸
(按视图/侧/行/大外小内排序) → 直径/半径尺寸 → 引出说明 → 参数覆盖检查。
所有冲突处理遵循"最少调整"：优先顺延候选位置并记入 Resolved.adjust，
放不下则记入 R1 警告，绝不静默丢弃。
