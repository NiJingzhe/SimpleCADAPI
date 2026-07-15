# Weaving Machine CAD

This directory contains an executable bottom-up representative model of the
complete multi-axial weaving-machine architecture. The default build contains:

- source-bearing concept parameters and explicit manufacturing gates;
- an authoritative inventory that preserves unresolved quantities;
- guide-index, phase, cumulative state, interlock, and yarn identity contracts;
- a D0 guide-block cartridge with a replaceable ceramic eye;
- a D0 replaceable wear rail with mounting holes;
- all fourteen stable A-level products from A00 through A90;
- the 2400 mm twin-datum-beam frame, supply rack, weaving gantry, take-up frame,
  and representative guarding;
- independent warp supply, upper/lower moving bias-package chains, fixed
  upper/lower two-row guide frames, and the M1 positive phase-lock drive;
- opposed binder needles, three common-carrier rapiers,
  engaging rods, an open-reed cassette, edge hooks/rails, and dual-screw linear
  take-up;
- explicit frame interfaces, bearing supports, guide rails, carriages, and
  brackets that connect every visible part to the A10 datum rails;
- a hard geometry support audit using transformed solid distance with a
  `0.25 mm` contact tolerance and no cross-subsystem incidental-contact edges;
- no visible warp, bias, filling, or formed-product process geometry;
- canonical model/session JSON, strict replay, semantic comparison, STEP,
  optional STL, four material-group inspection views, and a hash-bound evidence
  report containing each part's support parent.

The earlier D0 guide cartridge and D1 one-pitch Y-axis test fixture remain
available as an explicit debug target.

The fixture is not A40/A41 functional closure. `GAP-02` and `GAP-03` remain
open, so guide-block count, S0/S1/S2 occupancy, `FULL`, manufacturing release,
and D2-D5 claims fail closed.

## Run

From the repository root:

```bash
uv run python -m examples.21_weaving_machine.main \
  --target machine \
  --stl \
  --output-dir examples/out/weaving_machine
```

`machine` is the default target and exports the complete representative HOME
assembly. `--stl` is optional because STEP and model JSON preserve more CAD
information.

The command writes:

- `weaving_machine_a00_representative_home.model.json`
- `weaving_machine_a00_representative_home.session.json`
- `weaving_machine_a00_representative_home.step`
- `weaving_machine_a00_representative_home.stl` when `--stl` is supplied
- `weaving_machine.inventory.json`
- `weaving_machine_a00_representative_home.evidence.json`
- `weaving_machine_a00_representative_home.png` (isometric)
- `weaving_machine_a00_representative_home_front.png`
- `weaving_machine_a00_representative_home_right.png`
- `weaving_machine_a00_representative_home_top.png`

To build only the D1 guide test fixture:

```bash
uv run python -m examples.21_weaving_machine.main \
  --target fixture \
  --position 6 \
  --output-dir examples/out/weaving_machine_fixture
```

The fixture position is measured in millimetres along global `+Y`. Its closed
interval is `0...12 mm`; an out-of-range value fails unless
`--clamp-position` is explicitly supplied.

These commands intentionally fail with actionable gate messages:

```bash
uv run python -m examples.21_weaving_machine.main --detail full
uv run python -m examples.21_weaving_machine.main --manufacturing-gate
```

## Verify

```bash
uv run python -m pytest -q \
  test/test_example_21_weaving_machine_parameters.py \
  test/test_example_21_weaving_machine_topology.py \
  test/test_example_21_weaving_machine_state.py \
  test/test_example_21_weaving_machine_parts.py \
  test/test_example_21_weaving_machine_subassemblies.py \
  test/test_example_21_weaving_machine_structural_support.py
```

The current generated representative snapshot contains `369` visible leaf
parts. All `369` have an allowed contact chain to one of the two A10 datum
rails, with `610` allowed contact pairs at the fixed `0.25 mm` tolerance. The
canonical graph contains `1959` nodes and its model SHA-256 is
`ad4254f892919442ff0d5aea95f33213bc50705541c1c69bc853edb3591c06f5`.

The representative model is complete at the A-level architecture but is not a
manufacturing release. Repeated guide blocks, needles, reed blades, and supply
packages are intentionally downsampled while the separate inventory preserves
unresolved authoritative quantities. The SimpleCAD constraint solve is evidence
of placement propagation and connector residuals only. The support audit proves
current-pose solid proximity along restricted load-path edges; it is not a
fastener, stress, stiffness, fatigue, or dynamic-contact proof. `kinematics.py`
separately checks the declared joint, axis, limits, grounding path, and component
coverage; none of these results is a general constraint-rank, dynamics, wear,
or physical validation proof.
