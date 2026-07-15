# SimpleCADAPI Examples

Run examples from the repository root with `uv run python <path>`.
Generated STEP/STL/JSON files are written to `examples/out/`, which is ignored by git.

## Examples

- `01_basic_modeling.py` — functional shape modeling, booleans, and STEP/STL export.
- `02_graph_replay.py` — `GraphSession`, canonical model JSON export, and replay.
- `03_expressions.py` — expression parameters captured in a replayable model graph.
- `04_operation_output_ql.py` — kernel-proven feature output roles, projected source-binding/topology queries, strict output tagging, and replay validation.
- `05_loft_sweep_revolve.py` — profile operations: revolve, loft, and sweep.
- `06_parametric_gear_model.py` — lightweight involute spur gear model JSON example for replay/export tests.
- `07_serialization_operation_tree.py` — compact serialization demo showing how source calls map to canonical operation-tree nodes, including expressions, primitive lowering, features, booleans, transforms, patterns, and detail operations.
- `13_cycloidal_reducer.py` — compact 50 mm diameter, 10 mm tall, 10:1 cycloidal reducer assembly with twin segmented B-spline cycloidal discs, 180-degree opposed input eccentric cams, 18-degree half-lobe tooth-index phase, three-hole input/output disks, and assembly constraints.
- `14_ball_bearing.py` — parameterized ball bearing standard assembly with grooved inner/outer race rings, direct sphere rolling elements, stable ring component IDs, ring axis connectors, an inner-to-outer revolute constraint, and a demo shaft/housing bound through those connectors.
- `15_cached_mesh_obj_export.py` — developer-facing cached-mesh example that builds a normal Solid, bypasses the public STL exporter, reads the internal mesh cache, and writes a Wavefront OBJ file.
- `16_compact_two_stage_planetary_reducer/` — modular 58.8 mm diameter, 30 mm tall, 20:1 two-stage herringbone planetary reducer with through-bolted actuator housing bosses, sealed input/output end caps, realistic output register pads, reusable stdlib ball bearing placements, graph/model JSON replay, STEP export, solved gear constraints, and a `collision_probe.py` static verifier run.
- `17_static_collision_verifier.py` — static current-pose verifier example using internal cached meshes and python-fcl to report over-tolerance contact penetration.
- `18_leg_wheel_robot_dog_leg/` — planar leg-wheel module using three reused reducer actuator modules, a fixed motor-can part, a compact coaxial thigh/knee-drive actuator stack, a thigh output-flange-bolted upper link, a coaxial knee-drive output crank with 6-hole output flange pattern, a true parallelogram pushrod linkage whose knee-side `BB'` ear is integrated into the shank plate, knee bearing retainer holes, wheel-hub housing/output bolt circles, graph/model JSON replay, STEP/FCStd export, and a leg-level `collision_probe.py` packaging check.
- `19_four_planet_planetary_reducer/` — exposed single-stage 3.5:1 fixed-ring planetary gearset with one input sun gear, four equally spaced planet gears, an internal ring gear, a four-pin output carrier, solved revolute/external gear/internal belt-equivalent mesh constraints, graph/model JSON replay, STEP export, and FCStd export.
- `20_five_axis_desktop_robot_arm/` — five-revolute-axis desktop robot arm inspired by the reference image, using five reused Example 16 reducer actuator modules with an improved rear-service motor package, explicit part/interface validation before assembly, base yaw, shoulder/elbow/wrist pitch, tool roll, bolted housing/output flange interfaces, sensor face detail, graph/model JSON replay, STEP export, and FCStd export.
- `20_integrated_bldc_joint_actuator/` — compact 50 mm OD joint actuator with a real 12-slot/14-pole inner-rotor BLDC motor, integrated rotor-shaft/stage-1 sun, 20:1 two-stage herringbone planetary reducer, serviceable split housing, paired output bearings, circular ESC PCB, rear phase and power/CAN terminals, graph/model JSON replay, STEP export, and FCStd export.
- `21_weaving_machine/` — complete representative HOME assembly for a four-axial multilayer weaving machine, with all fourteen A00-A90 subsystems, geometry-audited support paths to the A10 datum rails, warp/bias supplies, two guide frames, three-channel rapiers, binder needles, engaging rods, open reed, edge hooks, dual-screw take-up, strict graph/model replay, STEP/STL export, four inspection views, and evidence-gated limitations. Visible process-yarn geometry is intentionally omitted.
- `22_city_block_diorama/` — colored static city-block diorama inspired by the reference image, with ten fully enclosed buildings, modeled interiors, roads, plaza, fountain, landscaping, street furniture, graph/model JSON replay, STEP/STL/FCStd export, and isometric screenshot output. Vehicles are intentionally excluded.
