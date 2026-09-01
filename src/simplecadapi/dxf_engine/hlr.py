"""dxf_engine.hlr — OCCT 隐藏线消除投影 (GB/T 4458.1 视图画法)。"""
from __future__ import annotations

import math

from OCP.BRepAdaptor import BRepAdaptor_Curve
from OCP.GCPnts import GCPnts_QuasiUniformDeflection
from OCP.GeomAbs import GeomAbs_Circle, GeomAbs_Line
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape
from OCP.TopAbs import TopAbs_EDGE
from OCP.TopExp import TopExp_Explorer
from OCP.TopoDS import TopoDS
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

DEG = 180.0 / math.pi


def hlr_project(shape, view_dir, x_dir):
    """单方向隐藏线消除。返回 (visible_edges, hidden_edges)。

    view_dir: 观察方向朝向物体的轴向; x_dir: 投影面内屏幕右方向。
    相切过渡线 (Rg1/RgN) 不取 —— 工程图不画光滑缝。
    """
    algo = HLRBRep_Algo()
    algo.Add(shape)
    algo.Projector(HLRAlgo_Projector(
        gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*view_dir), gp_Dir(*x_dir))))
    algo.Update()
    algo.Hide()
    hlr = HLRBRep_HLRToShape(algo)

    def _edges(compound):
        out = []
        if compound.IsNull():
            return out
        exp = TopExp_Explorer(compound, TopAbs_EDGE)
        while exp.More():
            out.append(TopoDS.Edge_s(exp.Current()))
            exp.Next()
        return out

    return (_edges(hlr.VCompound()) + _edges(hlr.OutLineVCompound()),
            _edges(hlr.HCompound()) + _edges(hlr.OutLineHCompound()))


def discretize_edge(edge, deflection=0.04):
    """边 -> (adaptor, 采样点列)。"""
    ad = BRepAdaptor_Curve(edge)
    t0, t1 = ad.FirstParameter(), ad.LastParameter()
    disc = GCPnts_QuasiUniformDeflection(ad, deflection, t0, t1)
    pts = []
    if disc.IsDone():
        for i in range(1, disc.NbPoints() + 1):
            p = disc.Value(i)
            pts.append((p.X(), p.Y()))
    else:
        for t in (t0, 0.5 * (t0 + t1), t1):
            p = ad.Value(t)
            pts.append((p.X(), p.Y()))
    dedup = [pts[0]]
    for q in pts[1:]:
        if math.dist(q, dedup[-1]) > 1e-6:
            dedup.append(q)
    return ad, dedup


def arc_angles(ad, cxy, t0, t1):
    """DXF 逆时针弧起止角; 采样中点落在弧段内的角度序为准。"""
    cx, cy = cxy
    p0, pm, p1 = ad.Value(t0), ad.Value(t0 + (t1 - t0) * 0.499999), ad.Value(t1)
    a0 = math.atan2(p0.Y() - cy, p0.X() - cx) * DEG
    am = math.atan2(pm.Y() - cy, pm.X() - cx) * DEG
    a1 = math.atan2(p1.Y() - cy, p1.X() - cx) * DEG
    norm = lambda a: a % 360.0

    def in_arc(beg, end, mid):
        beg, end, mid = norm(beg), norm(end), norm(mid)
        return beg <= mid <= end if beg <= end else (mid >= beg or mid <= end)

    a0n, a1n = norm(a0), norm(a1)
    return (a0n, a1n) if in_arc(a0n, a1n, norm(am)) else (a1n, a0n)
