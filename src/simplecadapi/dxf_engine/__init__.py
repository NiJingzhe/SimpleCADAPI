"""simplecadapi.dxf_engine — 声明式 GB 工程图纸引擎。

分层 (标注学 mindset):
  model    标注语义声明 —— 基准体系 / 定形·定位·总体尺寸 / 参数覆盖追溯
  planner  标注方案求解 —— 视图布局、行槽分配(小内大外)、最少调整、GB 规则 R1-R7
  hlr      OCCT 隐藏线消除投影 (GB/T 4458.1)
  render   手工基元渲染 —— 文字平行尺寸线(字头朝上/朝左)、实心箭头、细实线

GB/T 4458.4-2003 尺寸注法 · GB/T 4457.4-2002 图线 · GB/T 14692 投影法
"""
from .model import (CenterDecl, DatumDecl, DimDecl, LeaderDecl, SheetDecl,
                    ViewDecl)
from .planner import SheetPlan

__all__ = ["SheetDecl", "ViewDecl", "DimDecl", "DatumDecl", "CenterDecl",
           "LeaderDecl", "SheetPlan"]
