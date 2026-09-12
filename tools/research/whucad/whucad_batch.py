#!/usr/bin/env python3
"""Batch-translate the whole WHUCAD vec dataset into FTC .py sources.

Walks every h5 under --vec-root, decodes, translates, and writes one
``<uid>.ftc.py`` per model under --out (mirroring the 0000.../0103 folder
layout). Aggregates model/feature counts and prints a summary. The output
directory receives .py files only.

Usage:
    .venv/bin/python tools/research/whucad/whucad_batch.py \
        --vec-root /path/to/WHUCAD/data/vec --out /path/to/whucad_ftc_py \
        [--workers 8]
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any, Dict

_TOOLS = Path(__file__).resolve().parent
if str(_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TOOLS))

import whucad_vec as wvec  # noqa: E402
from whucad_to_ftc import translate_features  # noqa: E402


def translate_one(payload: Dict[str, Any]) -> Dict[str, Any]:
    src, dst = payload["src"], payload["dst"]
    stats: Dict[str, Any] = {"uid": payload["uid"], "ok": False}
    try:
        features = wvec.load_h5(src)
    except Exception as exc:  # noqa: BLE001
        stats["error"] = f"decode: {exc}"[:200]
        return stats
    stats["features_decoded"] = len(features)
    try:
        source = translate_features(features, payload["uid"])
    except Exception as exc:  # noqa: BLE001
        stats["error"] = f"translate: {exc}"[:200]
        return stats
    dst_path = Path(dst)
    dst_path.parent.mkdir(parents=True, exist_ok=True)
    dst_path.write_text(source)
    stats["ok"] = True
    stats["features_emitted"] = source.count("# ---- feature:")
    stats["features_skipped"] = source.count("# step ")
    kinds = Counter()
    for feature in features:
        kinds[getattr(feature, "kind", type(feature).__name__)] += 1
    stats["kinds"] = dict(kinds)
    return stats


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vec-root", type=Path, required=True,
                        help="root of the WHUCAD h5 tree, e.g. <clone>/data/vec")
    parser.add_argument("--out", type=Path, required=True,
                        help="output root; .py files land under <out>/<folder>/<uid>.ftc.py")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args(argv)

    jobs = []
    for h5 in sorted(args.vec_root.rglob("*.h5")):
        uid = f"{h5.parent.name}/{h5.stem}"
        dst = args.out / h5.parent.name / f"{h5.stem}.ftc.py"
        jobs.append({"src": str(h5), "dst": str(dst), "uid": uid})
    print(f"found {len(jobs)} h5 models under {args.vec_root}")

    if args.out.exists():
        shutil.rmtree(args.out)
    args.out.mkdir(parents=True, exist_ok=True)

    totals = {
        "models": len(jobs), "written": 0, "errors": 0, "empty": 0,
        "features_decoded": 0, "features_emitted": 0, "features_skipped": 0,
    }
    kinds_total: Counter = Counter()
    error_samples = []

    done = 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for stats in pool.map(translate_one, jobs, chunksize=64):
            done += 1
            if not stats["ok"]:
                totals["errors"] += 1
                if len(error_samples) < 10:
                    error_samples.append((stats["uid"], stats.get("error", "")))
                continue
            totals["written"] += 1
            totals["features_decoded"] += stats["features_decoded"]
            totals["features_emitted"] += stats["features_emitted"]
            totals["features_skipped"] += stats["features_skipped"]
            if stats["features_emitted"] == 0:
                totals["empty"] += 1
            for kind, count in stats["kinds"].items():
                kinds_total[kind] += count
            if done % 10000 == 0:
                print(f"  ... {done}/{len(jobs)}")

    print("\n==== 批量翻译汇总 ====")
    print(f"模型总数:        {totals['models']}")
    print(f"成功写出 .py:    {totals['written']}")
    print(f"解码/翻译错误:   {totals['errors']}")
    print(f"全跳过模型(空):  {totals['empty']}")
    print(f"特征总数(解码):  {totals['features_decoded']}")
    print(f"特征块(译出):    {totals['features_emitted']}")
    print(f"特征跳过(注记):  {totals['features_skipped']}")
    print("特征类型分布:", dict(sorted(kinds_total.items())))
    for uid, err in error_samples:
        print(f"  ! {uid}: {err}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
