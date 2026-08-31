"""agent_drawing: LLM-in-the-loop 出图驱动。

引擎只做评估(精确冲突数据)与动作校验, 布局决策由 agent 逐轮提交:
  uv run python agent_drawing.py eval [round1.json]
  uv run python agent_drawing.py render [roundN.json]
动作文件: {"u_link": [{op,name,...}, ...], "shell": [...]}
无状态: 每次从声明确定性重建 plan 并重放动作 —— 动作文件即决策日志。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import drawing as D  # noqa: E402
from simplecadapi.dxf_engine import SheetPlan  # noqa: E402


def main() -> None:
    cmd = sys.argv[1]
    acts = json.loads(Path(sys.argv[2]).read_text()) if len(sys.argv) > 2 else {}
    plans = {"u_link": SheetPlan(D.u_link_sheet()).solve(),
             "shell": SheetPlan(D.shell_sheet()).solve()}
    for sheet, plan in plans.items():
        for a in acts.get(sheet, []):
            res = plan.apply([a])["results"][0]
            tag = "OK" if res.get("ok") else "REJECTED"
            extra = "" if res.get("ok") else " " + json.dumps(
                {k: res[k] for k in ("violations", "corridors", "error") if k in res},
                ensure_ascii=False)
            print(f"[{sheet}] {res.get('element', a.get('op'))}: {tag}{extra}",
                  file=sys.stderr)
    if cmd == "eval":
        print(json.dumps({k: p.evaluate() for k, p in plans.items()},
                         ensure_ascii=False, indent=1))
    elif cmd == "viz":
        from simplecadapi.dxf_engine.agent import annotate_plan
        out = HERE / "out"
        for k, p in plans.items():
            ev = p.evaluate()
            annotate_plan(p, out / f"annotated_{k}.png", ev)
            print(f"[{k}] annotated_{k}.png warn={ev['n_warn']}", file=sys.stderr)
    elif cmd == "diff":
        # diff <before.json> <after.json>: 两版动作日志各自渲染后像素差分
        import tempfile

        import numpy as np
        from PIL import Image

        out = HERE / "out"
        for tag, acts in (("before", json.loads(Path(sys.argv[2]).read_text())),
                          ("after", json.loads(Path(sys.argv[3]).read_text())
                           if len(sys.argv) > 3 else {})):
            ps = {"u_link": SheetPlan(D.u_link_sheet()).solve(),
                  "shell": SheetPlan(D.shell_sheet()).solve()}
            for sheet, plan in ps.items():
                for a in acts.get(sheet, []):
                    plan.apply([a])
                plan.render(tempfile.mktemp(suffix=".dxf"),
                            out / f"_diff_{tag}_{sheet}.png")
        for sheet in ("u_link", "shell"):
            a = np.array(Image.open(out / f"_diff_before_{sheet}.png").convert("L"))
            b = np.array(Image.open(out / f"_diff_after_{sheet}.png").convert("L"))
            dark_a, dark_b = a < 160, b < 160
            rgb = np.full((*a.shape, 3), 255, np.uint8)
            rgb[dark_a & dark_b] = (185, 185, 185)     # 不变 → 灰
            rgb[dark_a & ~dark_b] = (0, 90, 255)       # 仅 before → 蓝 (移走)
            rgb[~dark_a & dark_b] = (255, 0, 0)        # 仅 after → 红 (移入)
            Image.fromarray(rgb).save(out / f"diff_{sheet}.png")
            print(f"[{sheet}] diff_{sheet}.png "
                  f"移入={int((~dark_a & dark_b).sum())}px "
                  f"移出={int((dark_a & ~dark_b).sum())}px", file=sys.stderr)
    elif cmd == "render":
        out = HERE / "out"
        plans["u_link"].render(out / "u_link_drawing.dxf", out / "u_link_drawing.png")
        plans["shell"].render(out / "shell_drawing.dxf", out / "shell_drawing.png")


if __name__ == "__main__":
    main()
