"""dxf_engine.model — 标注声明模型。

标注学分层 (GB/T 4458.4, GB/T 16675.1):
  基准体系   DatumDecl    —— 主基准/辅助基准, 定位尺寸的出发点
  尺寸语义   DimDecl.kind —— size(定形) / position(定位, 须引用基准) / overall(总体)
  几何语义   DimDecl.semantic —— linear / diameter / radius
  参数追溯   covers       —— 该尺寸承载哪些模型参数 (参数覆盖追溯 R5)
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ViewDecl:
    """HLR 投影视图。n=观察方向, xd=投影面内屏幕右方向; align 定义布局约束。"""
    name: str
    shape: object
    n: tuple
    xd: tuple
    align: dict = field(default_factory=dict)   # {"to","side","gap"} side: below|right
    anchor: tuple = None


@dataclass
class DimDecl:
    """一条尺寸声明。kind=定位(position)尺寸必须在 datum 里引用已声明基准。"""
    kind: str                     # size | position | overall
    view: str
    semantic: str                 # linear | diameter | radius
    caption: str                  # 参数名 (进入文本 "值 (caption)")
    value: float = None
    p1: tuple = None              # linear 测量点 (视图局部模型坐标)
    p2: tuple = None
    center: tuple = None          # dia/rad 圆心
    radius: float = None
    at: float = None              # dia/rad 方位角
    datum: str = None             # position/size 引用的基准字母
    side: str = None              # bottom/right/left/top
    row: int = 0                  # 期望行 (同侧行距, 碰撞顺延)
    out: float = 8.0              # dia/rad 文本外伸
    dec: int = 0
    prefix: str = ""
    covers: list = field(default_factory=list)   # 承载的模型参数名
    name: str = ""

    def __post_init__(self):
        if self.semantic == "linear" and self.kind == "position" and not self.datum:
            raise ValueError(f"定位尺寸 {self.caption or self.name} 未声明基准")
        if self.covers and self.caption not in self.covers:
            self.covers = [self.caption] + list(self.covers)


@dataclass
class DatumDecl:
    """基准符号声明（GB 基准体系）：主基准 A、辅助基准 B/C…。"""
    letter: str                   # A(主) B C...
    kind: str                     # axis | plane
    view: str
    at: tuple                     # 视图局部模型坐标
    box_off: tuple = (9.0, 6.0)
    desc: str = ""


@dataclass
class CenterDecl:
    """中心线声明：p1/p2 直线中心线，或 arc=(cx,cy,r,a0,a1) 圆弧中心线。"""
    view: str
    p1: tuple = None
    p2: tuple = None
    arc: tuple = None             # (cx, cy, r, a0, a1) 视图局部模型坐标


@dataclass
class LeaderDecl:
    """引出说明声明：从 anchor 引出折线到注释文本。"""
    view: str
    anchor: tuple
    lines: list
    off: tuple = (30.0, -18.0)
    alt_offs: list = field(default_factory=list)
    dx_dir: float = 1.0
    name: str = ""


@dataclass
class SheetDecl:
    """一张图纸的完整声明：图幅信息 + 视图 + 基准 + 尺寸 + 中心线 + 引出说明 + 参数表。

    调用方只声明"要表达什么"，不指定任何纸面坐标；布局与标注位置由
    SheetPlan.solve() 求解。front/anchor 定义主视图锚定，其余视图经
    ViewDecl.align 相对主视图对正（第一角投影，长对正/高平齐）。
    """
    title: str
    dwg_no: str
    scale: float
    front: str
    anchor: tuple
    views: list
    datums: list = field(default_factory=list)
    dims: list = field(default_factory=list)
    centers: list = field(default_factory=list)
    leaders: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    params: dict = field(default_factory=dict)
    material: str = "PLA-CF / PAHT"
    notes_zone: tuple = (25.0, 5.0, 232.0, 90.0)   # x0,y0,x1,y1 (正序)
