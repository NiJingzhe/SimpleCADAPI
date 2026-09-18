#!/usr/bin/env python3
"""Profile WHUCAD vector data: feature/curve/extent/select-shape distributions
and which forms the FTC translator supports.

Run over any set of h5 files (a sampled folder is enough):

    .venv/bin/python tools/research/whucad/whucad_profile.py \
        /path/to/WHUCAD/data/vec/0000 [--limit N] [--out PATH]
"""

from __future__ import annotations

import argparse
import collections
import json
import sys
from glob import glob
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

import whucad_select as wsel  # noqa: E402
import whucad_to_ftc  # noqa: E402
import whucad_vec as w  # noqa: E402


def profile_path(path: str, limit: Optional[int] = None) -> dict:
    stats: dict = {}
    counters = {key: collections.Counter() for key in (
        "feature_kinds", "curves", "extent_types", "rev_axis", "rev_angles",
        "shell_forms", "select_shapes", "unsupported", "model_status",
        "features_per_model", "loops_per_sketch")}

    paths = sorted(glob(str(Path(path) / "*.h5")))
    if limit:
        paths = paths[:limit]

    for h5_path in paths:
        try:
            features = w.load_h5(h5_path)
        except Exception as exc:  # noqa: BLE001
            counters["model_status"][f"decode_error: {type(exc).__name__}"] += 1
            continue
        counters["features_per_model"][len(features)] += 1
        translated = whucad_to_ftc.Translator(features, "profile")
        emittable = 0
        for index, feature in enumerate(features):
            counters["feature_kinds"][feature.kind] += 1
            if isinstance(feature, w.ExtrudeFeature):
                counters["extent_types"][f"{feature.extent_type1}/{feature.extent_type2}"] += 1
                counters["loops_per_sketch"][len(feature.sketch.profile.loops)] += 1
                for loop in feature.sketch.profile.loops:
                    for curve in loop.curves:
                        counters["curves"][type(curve).__name__] += 1
            if isinstance(feature, w.RevolveFeature):
                axis = feature.axis_select
                counters["rev_axis"][f"{axis.select_type}/{axis.body_type}"] += 1
                counters["rev_angles"][f"two_sided={feature.angle_two > 1e-9}"] += 1
                for loop in feature.sketch.profile.loops:
                    for curve in loop.curves:
                        counters["curves"][type(curve).__name__] += 1
            if isinstance(feature, w.FinishFeature) and feature.kind == "Shell":
                counters["shell_forms"][f"external_thickness={feature.params['second_thickness'] > 1e-9}"] += 1
            if isinstance(feature, w.FinishFeature):
                for select in feature.select_list:
                    counters["select_shapes"][_select_shape(feature.kind, select)] += 1
            try:
                translated._emit_feature(index, feature)
                emittable += 1
            except (whucad_to_ftc.UnsupportedForm, wsel.UnsupportedSelect) as exc:
                counters["unsupported"][f"{feature.kind}: {exc}"] += 1
        counters["model_status"]["ok" if emittable == len(features) else "partial"] += 1

    for key, counter in counters.items():
        stats[key] = dict(counter.most_common())
    stats["scanned"] = len(paths)
    return stats


def _select_shape(kind: str, select: w.Select, depth: int = 0) -> str:
    if depth > 2:
        return "..."
    shape = f"{kind}:{select.select_type}/{select.body_type}"
    if select.operation_list:
        shape += "(" + ",".join(_select_shape(kind, s, depth + 1) for s in select.operation_list) + ")"
    return shape


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("vec_dir")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)

    stats = profile_path(args.vec_dir, args.limit)
    text = json.dumps(stats, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text)
        print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
