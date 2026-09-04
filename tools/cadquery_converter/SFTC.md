# SimpleCAD Feature Tree Convention (SFTC)

SFTC is the **canonical SimpleCADAPI training-output format**: constrained Python
source whose structure maps directly to CAD feature managers.

**Scope (important):**

| Layer | What it is | Current status |
| --- | --- | --- |
| **SFTC (target)** | Parameters + Feature Tree + Export using `skills/simplecadapi` | **Defined** — this document |
| **CadQuery adapter** | CQ trace / AST → SFTC | **Implemented** — `tools/cadquery_converter/` |
| **DeepCAD JSON adapter** | sequence/graph JSON → SFTC | **Not implemented** (future front-end) |
| **HistCAD JSON adapter** | history JSON → SFTC | **Not implemented** (future front-end) |
| **Build123d / paper FTC adapter** | Build123d FTC source → SFTC | **Not implemented**; we only **borrow FTC layout ideas**, not Build123d syntax |

SFTC is **not** CadQuery-specific syntax—it is **SimpleCAD-native** code. CadQuery is
today's primary **ground-truth source** for BenchCAD; other formats should lower into a
shared feature IR, then emit the **same** SFTC shell (`sftc_template.py`).

Paper FTC (Build123d) is a **parallel precedent**, not an input we consume. If multiple
sources converge on SFTC, validation compares each source's semantics to the **same**
SimpleCAD solid and feature-tree structure—not to each other.

---

SFTC plays the same **role** as the paper's Feature Tree Convention (FTC) for Build123d:
a **fixed, constrained subset** of a Python CAD API whose structure maps directly to
commercial CAD feature managers (Onshape, SolidWorks, Fusion 360).

SFTC is **not** a Build123d clone. The primary authority is
`skills/simplecadapi/SKILL.md`. We take from FTC only the **structural idea**—three
mandatory sections, ordered features, named parameters, explicit export—and express
it with **SimpleCAD-native** APIs (`@scad.model`, `scad.var`, `extrude_rsolid`, …).

---

## 1. Why two paradigms?

| Paradigm | What it encodes | Role in pipeline |
| --- | --- | --- |
| **CadQuery** | Workplane chains: plane → sketch/profile → feature → boolean → modifier | **Ground truth** (BenchCAD source) |
| **SFTC** | Parameters + labeled feature blocks + SimpleCAD ops | **Training target** (generated `.sftc.py`) |
| **CAD feature manager** | Sketch + Extrude + Cut + Fillet + … | **Semantic target** (downstream IR / translation) |

CadQuery and SFTC are both **paradigms**, not arbitrary Python:

- CadQuery: implicit stack of workplanes, profiles, and solids.
- SFTC: explicit ordered list of `# Feature N:` blocks, each with reference frame,
  profile (when needed), operation, and dependency on prior `body`.

The converter's job is **paradigm-preserving translation**: each meaningful CadQuery
step should become one readable SFTC feature block, not a collapsed opaque script.

---

## 2. Design principles (FTC-aligned, SimpleCAD-first)

Commercial CAD organizes models as **feature trees**: ordered operations with a
reference plane, sketch or modifier, parameters, and dependencies.

SFTC enforces this through **three mandatory sections**:

### 2.1 Parameters section

All tunable dimensions → `scad.var(name=..., default=..., unit="mm", comment=...)`.

- Ensures **editability**: changing a var propagates through replay and graph JSON.
- Matches SimpleCAD skill rule: exposed tunables MUST be `Var` declarations.
- Layout/placement constants may remain literals inside the feature that uses them.

### 2.2 Feature Tree section

Single `@scad.model(graph_id=...)` entry point containing **labeled features**:

```text
# Feature N: <human description>
<optional profile construction>   # sketch equivalent
<feature operation>               # extrude / cut / fillet / …
<optional result_tag=...>       # graph / FeatureGraphIR anchor
```

Each block ≈ **one entry** in a CAD feature manager.

- Profile + feature op mirror **BuildSketch + extrude** in paper FTC, but use
  `make_*_rface` / wire builders + `extrude_rsolid` instead of Build123d syntax.
- Workplane context → `scad.SimpleWorkplane(...)` or traced plane frame on profiles.
- Unsupported CadQuery patterns → `# SFTC_UNSUPPORTED: ...` in source + meta JSON.

### 2.3 Export section

- Grounding: `print('volume', …)` inside `build_model()`.
- `scad.capture_result(value=body)` and return final solid.
- `main()` exports STEP via `scad.export_step(...)`.

---

## 3. SFTC formal grammar

Paper FTC uses `BuildPart` + `BuildSketch`. SFTC uses `@scad.model` + functional ops.

```python
# Listing: SimpleCAD Feature Tree Convention structure

from pathlib import Path
import simplecadapi as scad
from simplecadapi import ql          # optional, when selectors emitted

# -- Parameters --
<name> = scad.var(name=<name>, default=<float>, unit="mm"[, comment=<str>])
...

OUT = Path("out")

# -- Feature Tree --
@scad.model(graph_id=<part_id>)
def build_model():
    # Feature 1: <description>
    [<with scad.SimpleWorkplane(origin=..., normal=..., x_dir=...):>]
    <profile> = scad.make_<primitive>_rface(...) | wire_path → face
    <body|solid_k> = scad.extrude_rsolid(
        profile=<profile>, direction=..., distance=<var|float>,
        [, result_tag="feature.<slug>.n<N>"]
    )

    # Feature 2: <description>  (modifier)
    <body> = scad.fillet_rsolid(
        solid=<body>, edges=<ql.select(...)|get_edges(...)>, radius=<var>,
        result_tag="feature.fillet.n<N>",
    )

    # Feature 3: <description>  (boolean cut)
    <tool_* profile + extrude | sweep | primitive>
    <body> = scad.cut_rsolid(<body>, <tool_solid>)

    # Feature K: <description>  (pattern)
    for _pt in [...]:
        <tool> = ...
        <body> = scad.cut_rsolid(<body>, <tool>)

    print("volume", round(<body>.get_volume(), 3))
    scad.capture_result(value=<body>)
    return <body>

# -- Export --
def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = build_model()
    scad.export_step(shapes=result.value, filename=str(OUT / "<part_id>.step"))

if __name__ == "__main__":
    main()
```

**MUST rules** (from SimpleCAD skill + SFTC):

1. One part per file; one `@scad.model` entry point.
2. Keyword arguments only on every SimpleCAD public API call.
3. Each logical CAD step starts with `# Feature N: ...`.
4. Exposed tunables use `scad.var(...)` in the Parameters section.
5. End with `capture_result` + return final solid; export in `main()`.
6. Never emit raw CadQuery selector strings; use `ql.select(...).where(...)` when needed.
7. Prefer functional ops (`make_*`, `extrude_rsolid`, `cut_rsolid`, …).

---

## 4. Three-way mapping

### 4.1 CadQuery (traced) → SFTC → CAD feature manager

| CadQuery (runtime trace) | SFTC block pattern | CAD feature manager |
| --- | --- | --- |
| `Workplane` + `circle` + `extrude` | profile + `extrude_rsolid` | Sketch + Extrude |
| `Workplane` + `rect` / `polyline` + `extrude` | wire/face profile + `extrude_rsolid` | Sketch + Extrude |
| `box` / `cylinder` / `sphere` | `make_*_rsolid` in `SimpleWorkplane` | Primitive |
| `revolve` | profile + `revolve_rsolid` | Revolve |
| `loft` | profiles + `loft_rsolid` | Loft |
| `sweep` | profile + path wire + `sweep_rsolid` | Sweep |
| `hole` / `cutThruAll` / `cutBlind` | profile tool + `cut_rsolid` | Hole / Cut / Pocket |
| `cut` / `union` (nested `Workplane`) | tool sub-chain + boolean | Cut / Join |
| `fillet` / `chamfer` | `fillet_rsolid` / `chamfer_rsolid` | Fillet / Chamfer |
| `rarray` + `pushPoints` + cut | `for` loop + repeated `cut_rsolid` | Pattern + Cut |

### 4.2 Paper FTC → SFTC (what we borrow vs replace)

| Paper FTC (Build123d) | SFTC (SimpleCAD) |
| --- | --- |
| `# -- Parameters --` + Python `float` vars | `# -- Parameters --` + `scad.var(...)` |
| `with BuildPart() as part:` | `@scad.model` + `def build_model():` |
| `# Feature N:` | `# Feature N:` (same) |
| `with BuildSketch(Plane):` | `make_*_rface` / wire → face (+ optional `SimpleWorkplane`) |
| `extrude(amount=...)` | `extrude_rsolid(profile=..., direction=..., distance=...)` |
| `mode=Mode.SUBTRACT` | separate tool solid + `cut_rsolid(body, tool)` |
| `fillet(edges, r)` | `fillet_rsolid(solid=body, edges=..., radius=...)` |
| `result = part.part` | `capture_result(value=body); return body` |
| `export(result, "*.step")` | `scad.export_step(...)` in `main()` |

### 4.3 SFTC → FeatureGraphIR (downstream)

Each `# Feature N:` block with a committing op and optional `result_tag` is one node:

| SFTC commit op | IR feature kind |
| --- | --- |
| `extrude_rsolid` | `Extrude` |
| `cut_rsolid` | `Cut` |
| `union_rsolid` | `Join` |
| `revolve_rsolid` | `Revolve` |
| `loft_rsolid` | `Loft` |
| `sweep_rsolid` | `Sweep` |
| `fillet_rsolid` / `chamfer_rsolid` | `Fillet` / `Chamfer` |

`result_tag="feature.<slug>.n<N>"` links source text ↔ graph node ↔ trace step index
(when alignment metadata is emitted).

---

## 5. CadQuery paradigm ↔ SFTC paradigm

CadQuery is already a feature-tree-like stack, just implicit:

```text
CQ:  Workplane("XY") → circle(r) → extrude(h) → faces(">Z") → hole(d) → chamfer(c)
SFTC:
  Feature 1: extrude circle     (plane frame + make_circle_rface + extrude_rsolid)
  Feature 2: through hole       (face workplane + cut_rsolid)
  Feature 3: chamfer            (ql/get_edges + chamfer_rsolid)
```

**Tracer path (recommended):** record CQ ops at runtime → replay emits SFTC blocks
in order. The trace is the **alignment anchor** between ground truth and generated code.

**Static AST path (legacy):** parse CQ source → IR → emit SFTC; less accurate for
selectors and plane frames.

`model.json` from executing SFTC is a **validation sidecar** (graph replay check), not
the translation hub.

---

## 6. Validation: measuring gap to ground truth

Acceptance should be **multi-layer**, not volume-only:

| Layer | Question | Signals |
| --- | --- | --- |
| **Structure** | Did each CAD feature semantic (Extrude/Hole/…) emit as a `# Feature N:` block? | `feature_coverage`, unsupported semantics, feature count — **not** CQ API step 1:1 |
| **Parameters** | Do `scad.var` defaults match traced numeric args? | param match rate |
| **Geometry** | Does the final solid match CQ? | volume, bbox; optionally face/edge count, BREP compare |

Suggested training tiers:

| Tier | Structure | Geometry | Use |
| --- | --- | --- | --- |
| **A** | feature_coverage ≥90%, no critical unsupported | vol ≤2%, bbox ≤5% | Primary SFT training |
| **B** | feature_coverage ≥70% | vol ≤5% | Hard cases / geometry-only supervision |
| **C** | partial / format-only | executes | Style reference only |
| **reject** | exec fail or no solid | — | Drop or fix converter |

`feature_coverage` counts **CAD feature units** (profile ops fold into the committing Extrude/Cut/…); context ops (`faces`/`workplane`) are not features.

Volume-only `accepted` is necessary but **not sufficient** for feature-aligned training.


---

## 7. What SFTC is not

- Not Build123d `BuildPart` / `BuildSketch` / `Mode.SUBTRACT` syntax.
- Not a mandate to wrap every sketch in nested context managers (use when plane frame requires it).
- Not a replacement for SimpleCAD graph JSON—SFTC is human/LLM-readable source;
  `model.json` remains machine interchange for replay and translation.

---

## 8. Multi-source architecture (planned)

```text
                    ┌─────────────────┐
  CadQuery code ──► │ CQ tracer/replay│──┐
                    └─────────────────┘  │
  DeepCAD JSON  ──► │ deepcad → IR      │──┼──► FeatureProgram / alignment
  HistCAD JSON  ──► │ histcad → IR      │──┤         │
  Build123d FTC ──► │ b123d → IR        │──┘         ▼
                    └─────────────────┘      emit_sftc_module()
                                                    │
                                                    ▼
                                              *.sftc.py  (SFTC)
                                                    │
                                                    ▼
                                         build_model() → model.json
```

- **One target, many adapters.** SFTC grammar and SimpleCAD skill rules are stable.
- **Per-source validation:** ground truth runs in the source domain (CQ exec, JSON
  replay, etc.); target runs `build_model()`; compare structure + geometry.
- **Shared IR (optional middle):** `FeatureProgram` in `ir.py` already exists for
  static CQ; trace replay currently emits SFTC directly. Future adapters can share
  this IR or a richer FeatureGraphIR before emission.

---

## 9. Converter implementation (CadQuery today)

| Component | Role |
| --- | --- |
| `tracer/` | Record CQ ground-truth ops + plane frames + selections |
| `replay/trace_replay.py` | Trace → SFTC feature blocks (mapping in §4.1) |
| `sftc_template.py` | Emit Parameters / Feature Tree / Export shell |
| `validate.py` | Geometry layer (CQ vs SFTC metrics) |
| `SFTC.md` (this file) | Normative output standard |

When extending replay, always ask: **which `# Feature N:` does this CQ op become,
and which CAD feature manager entry does that block represent?**
