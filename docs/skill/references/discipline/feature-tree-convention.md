# Discipline: Feature Tree Convention (FTC)

Part sources are block-structured feature chains: every block is one feature
in the sense of a commercial CAD feature tree (Onshape / SolidWorks /
Fusion 360), readable by humans and LLMs, and translatable by the package
translators. This convention is mandatory for every part source authored in
any workflow.

## The paradigm

A part is a chain of blocks, each block being one step of:

```text
sketch  →  basic body build op  →  bool  →  modifier
```

expressed as explicit dataflow — each application call rebinds the body:

```python
body = scad.sweep_rsolid(profile=..., path=...)      # build
body = scad.cut_rsolid(body, tools)                  # subtract
body = scad.union_rsolid(body, bosses)               # add
body = scad.fillet_rsolid(solid=body, edges=sel, radius=r)  # modify
```

There is no accumulator object and no hidden state: inputs are explicit,
the recorded graph mirrors the source structure, and a failed operation
names one feature.

## Block header comments (mandatory)

Every block opens with a boundary comment; the next header closes the
previous block. One block = its tool/profile construction + exactly one
application call that rebinds the body (the first `build` block returns it).

```python
# ---- feature: base-plate (build, profile=sketch) ----
# ---- feature: motor-pockets (subtract, profile=geometry) ----
# ---- feature: boss-columns (add) ----
# ---- feature: cable-windows (subtract, profile=sketch) ----
# ---- feature: global-fillet (modify) ----
# ---- feature: mount-face-names (annotate) ----
```

- Fixed parseable form: `# ---- feature: <slug> (<role>) ----`.
- `<role>` is a closed vocabulary: `build | add | subtract | intersect |
  modify | pattern | annotate`.
- `<slug>` is the stable identity of the feature — no sequence numbers
  (source order is the feature order; numbers rot when features are
  inserted or reordered).
- Add a tier annotation when the block constructs new 2D input:
  `profile=sketch|geometry` and/or `path=sketch|geometry`.
- Block-local helpers live next to the block and carry the slug in their
  name (`_motor_pocket_tools`).

## Tier rules — where each authoring API is legal

**Sketch tier (default).** Closed planar profiles consumed by extrude,
revolve, or loft sections are authored in the sketch API with constraints
carrying the design intent, promoted via `make_face_from_sketch_rface`.
Never transcribe hand-computed coordinates for a parametric profile —
tangency and relational dimensions are constraints, not arithmetic
(`constrain_tangent_rsketch(..., at_a=..., at_b=...)` replaces hand-derived
arc midpoints).

**Planar sweep paths are sketch tier.** A planar path (open chain) is a
constrained sketch promoted with `make_wire_from_sketch_rwire` —
closedness is a consumer contract, so an open chain promotes fine and
`sweep_rsolid` accepts it; extrude/revolve/face builders reject open
wires at the point of use. Annotate `path=sketch`.

**Geometry tier (only these three cases).**

1. Non-planar paths and 3D curves — `make_helix_redge`, 3D splines; the
   sketch API is planar-only. Annotate `path=geometry`.
2. Transcribed or imported geometry whose constraints are unknown
   (reverse engineering, dataset conversion). Annotate
   `profile=geometry` — honestly, so the lost intent is visible.
3. Pure tool bodies whose shape **is completely contained in a basic
   primitive form** — a cut box that is just a box, a boss column that
   is just a cylinder (`make_box_rsolid`, `make_cylinder_rsolid`).
   Primitives are legal exactly when the design shape is fully expressed
   by the primitive and nothing more; a primitive is never a shortcut
   for a profiled feature. If the shape needs a profile, author a sketch.

## Selections inside blocks

`modify` blocks select through QL selectors — predicates plus cardinality
(`.take(n).exactly(n)`) — or tags. Bare topology enumeration does not
exist (plural getters are index-only); selections that escape the graph
capture kernel artifacts and do not translate. Indexed picks are reserved
for intentional, named choices.

## Ordering and failure

Follow `feature-ordering.md` for block order (base → additive →
subtractive → shell → through-holes → fillets/chamfers last): fragile
operations late, one named feature per block so a failure localizes to
one header. Parameter guards (`assert`-style feasibility checks on
design parameters) stay in the source; geometric verification never does
— it lives in the external verification scripts per
`geometric-validation.md`.

## The `@scad.part` decorator and its cache

`@scad.part` accepts keyword parameters only; emitted corpus sources state
them explicitly so the meaning is legible from the source itself:

- `id` — logical part identity (defaults to the function name); part of the
  cache key.
- `revision` — `'1.0.0'` by default; bump it to force rebuilds; part of the
  cache key.
- `inputs` — sequence of `file_input()` declarations; the referenced files'
  content snapshots enter the cache key.
- `cache` — cache policy: `"auto"` (read/write), `"off"`, `"read_only"`,
  `"read_write"`, `"refresh"`, or a policy dict / `CachePolicy`.
- `project_root` — anchor for the part cache, file inputs, and project
  config. Default: the directory containing the builder's source file —
  a script is its own project, runs from anywhere, and its cache lands
  beside it. Pass it explicitly only to anchor at a larger project
  (project-level cache or `[tool.simplecadapi.cache]` config).
- `tolerance_profile` — kernel tolerance fingerprint (default
  `'simplecad-default'`); part of the cache key.

**Where the cache lands.** The cache root is `<anchor>/.simplecad/cache`
(`records/`, `objects/`, `locks/`, `quarantine/`); part interface state
lives beside it at `<anchor>/.simplecad/state/latest-parts.json` and
follows the cache root. Overrides resolve as decorator `cache=` >
environment (`SIMPLECAD_CACHE_DIR`, `SIMPLECAD_CACHE_MODE`, …) >
`[tool.simplecadapi.cache]` in the `pyproject.toml` at the anchor >
defaults. The cache key covers `id`, `revision`, `tolerance_profile`,
normalized call arguments, the whole-file source fingerprint, file-input
snapshots, and the generator profile (SDK/OCC versions) — any source edit
invalidates.

**Delivered sources state the anchor explicitly.** A translator-emitted
or standalone `.ftc.py` passes `project_root=Path(__file__).parent`
explicitly so the cache location is legible from the source itself —
even though it matches the default, the corpus states it rather than
relying on implicit resolution.

## Reference shape of a compliant source

```python
# ---- params ----
PLATE_T = scad.var("plate_t", 6.0, unit="mm")
...

def _pocket_tools(p):
    ...  # block-local, geometry tier when tools are pure primitives

@scad.part(id="motor-mount", revision="1.0.0",
           project_root=Path(__file__).parent)
def build_motor_mount() -> scad.Part:
    # ---- feature: base-plate (build, profile=sketch) ----
    s = scad.make_sketch_rsketch(name="base", plane="XY")
    ...  # constrained rectangle, promoted to face
    body = scad.extrude_rsolid(profile=face, direction=(0, 0, 1), distance=PLATE_T)

    # ---- feature: motor-pockets (subtract, profile=geometry) ----
    body = scad.cut_rsolid(body, _pocket_tools(p))

    # ---- feature: mount-fillet (modify) ----
    body = scad.fillet_rsolid(
        solid=body,
        edges=ql.edges().where(ql.and_(
            ql.prop("geom.type", "==", "CIRCLE"),
            ql.prop("geom.center.z", ">=", ...),
        )).exactly(2),
        radius=FILLET_R,
    )
    ...
```

Each Onshape-style feature tree entry maps to exactly one header here —
that one-to-one mapping is the acceptance criterion for a compliant
source.
