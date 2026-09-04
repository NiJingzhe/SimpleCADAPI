# CadQuery → SimpleCADAPI (SFTC) converter

Convert CadQuery ground-truth programs into **SimpleCAD Feature Tree Convention
(SFTC)** Python, aligned with `skills/simplecadapi/SKILL.md`.

See [SFTC.md](./SFTC.md) for the output code standard.

## Setup

```bash
# Do not change the repo's .python-version (official pin is 3.10).
# CadQuery 2.8 needs Python >=3.11 and matches main cadquery-ocp 7.9 —
# pass --python 3.11 explicitly for converter work only.
uv sync --python 3.11 --group dev
uv pip install 'cadquery==2.8.0' pyarrow

# Always use the same interpreter afterwards, e.g.:
#   uv run --python 3.11 python ...
```


## Single file

```bash
PYTHONPATH=tools/cadquery_converter uv run python -m cadquery_converter convert \
  --input sample.cq.py \
  --output sample.sftc.py \
  --validate
```

## BenchCAD batch + filter

Dataset path (WSL):

```text
/mnt/c/Users/zhuxi/Documents/data/BenchCAD
```

**Static AST converter** (legacy / preview):

```bash
PYTHONPATH=tools/cadquery_converter uv run python -m cadquery_converter benchcad \
  --validate \
  --dataset /mnt/c/Users/zhuxi/Documents/data/BenchCAD \
  --output-dir /tmp/benchcad_sftc \
  --limit 1000 \
  --filter-quality accepted partial \
  --report /tmp/benchcad_report.json
```

**Runtime tracer** (recommended — records actual CQ ops + resolved face/edge fingerprints):

```bash
PYTHONPATH=tools/cadquery_converter uv run python -m cadquery_converter benchcad-traced \
  --validate \
  --export-model-json \
  --dataset /mnt/c/Users/zhuxi/Documents/data/BenchCAD \
  --output-dir /tmp/benchcad_traced \
  --limit 200 \
  --filter-quality accepted \
  --report /tmp/benchcad_traced_report.json
```

Outputs per row: `{stem}.sftc.py`, `{stem}.meta.json`, and optionally `{stem}.model.json`
(replay sidecar for validation, not a translation hop).

## Validation tiers

When `--validate` is enabled, each row runs **both** CadQuery source and generated
SimpleCAD code, then compares:

| Tier | Criteria |
| --- | --- |
| `accepted` | conversion ok, both executables succeed, volume error ≤ 2%, bbox error ≤ 5% |
| `partial` | executes but has unsupported-op notes or looser conversion status |
| `rejected` | parse/lowering failure, exec failure, or geometry mismatch beyond thresholds |

Use `--filter-quality accepted` to write only training-ready rows.

Meta sidecar `{stem}.meta.json` stores conversion + validation payload.

## Coverage

Deterministic lowering for common BenchCAD ops:

- primitives: `box`, `cylinder`, `sphere`
- profiles: `circle`, `rect`, `polygon`, `polyline`, `moveTo/lineTo/threePointArc/close`
- features: `extrude`, `cutBlind`, `revolve`, `loft`, `hole`, `cutThruAll`
- booleans: `cut`, `union`, `intersect` with nested `Workplane`
- modifiers: `chamfer`, `fillet`
- patterns: `rarray` + `rect` pocket cuts
- placement: `transformed(offset=...)`, `workplane(offset=...)`

Still reported as unsupported when present: `sweep`, `shell`, `slot2D`, `ellipse`,
complex selectors (`>Z or <Z`), `polarArray`, `pushPoints` holes.

## Tests

```bash
uv run python -m unittest discover -s test -p 'test_cadquery*.py' -v
```
