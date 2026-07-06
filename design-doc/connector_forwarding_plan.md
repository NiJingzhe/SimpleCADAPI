# Connector and Forwarding Plan

This document defines the planned direction for more flexible connector authoring,
assembly-level connector forwarding, solver behavior, and FreeCAD translation.
The immediate motivating case is a standard ball bearing subassembly used as a
component in a reducer assembly: the bearing already owns `inner_ring.axis` and
`outer_ring.axis`, but the parent assembly cannot currently bind those internal
connectors without either manually expanding the bearing or adding ad hoc wrapper
geometry.

## Problem Statement

`Part` and `Assembly` already both support `connectors`, and
`add_connector_rassembly(...)` can attach connector datums to an `Assembly`.
However, the current public connector model is still too narrow for reusable
mechanical subassemblies.

Current limitations:

- `Connector` is anchored by `GeometryRef`, so a connector is normally derived
  from a selected face, edge, vertex, wire, or solid.
- `ConnectorRef` is one-level only: `component_id + connector_id`.
- A parent assembly can reference connectors exposed by a direct component, but
  it cannot directly address an internal child connector such as
  `input_bearing.inner_ring.axis`.
- A reusable subassembly can contain useful internal connectors, but those
  connectors are not automatically exposed as the subassembly's public interface.
- FreeCAD export can represent Part and Assembly product trees, but it needs a
  deterministic way to emit forwarded assembly datums and bind constraints to
  them.

The desired behavior is that a standard bearing factory can expose `inner_axis`
and `outer_axis` as public connectors on the bearing assembly, while internally
mapping them to `inner_ring.axis` and `outer_ring.axis`.

## Design Goals

- Allow users and standard-library factories to define connectors without always
  selecting BREP topology.
- Allow an `Assembly` to expose stable public connectors that forward to internal
  component connectors.
- Keep the parent assembly constraint surface simple: direct component connector
  refs should continue to work.
- Avoid requiring parent assemblies to know the private product structure of a
  reusable subassembly.
- Make model JSON replay and FreeCAD translation deterministic.
- Avoid fragile FreeCAD edge/face re-selection when a connector can instead be
  represented as a composed coordinate frame.
- Preserve the current simple `make_connector_ref_rconnectorref(component_id,
  connector_id)` workflow for first-phase implementation.

## Connector Anchor Model

The current `Connector` stores a `GeometryRef`. The planned model is to generalize
the connector anchor while keeping a connector as a semantic datum frame.

Planned anchor kinds:

- `geometry`: the current behavior, derived from `GeometryRef` and BREP
  topology.
- `placement`: a direct datum frame in the owning `Part` or `Assembly` local
  coordinate system.
- `forwarded`: a connector frame forwarded from a component connector inside an
  assembly.

The connector should remain immutable and serializable. Its placement is still
resolved lazily from the anchor, because graph replay and translator backends
must derive the same frame from the same source data.

Proposed conceptual shape:

```python
Connector(
    connector_id="inner_axis",
    anchor=ConnectorAnchor(
        anchor_kind="forwarded",
        source_component_id="inner_ring",
        source_connector_id="axis",
        offset=None,
    ),
    name="Forwarded inner ring axis",
)
```

## Public API Plan

Keep existing APIs:

```python
make_face_connector_rconnector(...)
make_edge_connector_rconnector(...)
make_vertex_connector_rconnector(...)
add_connector_rpart(...)
add_connector_rassembly(...)
make_connector_ref_rconnectorref(...)
```

Add direct placement connectors:

```python
make_placement_connector_rconnector(
    connector_id: str,
    placement: Placement,
    name: str | None = None,
) -> Connector
```

Add assembly connector forwarding:

```python
forward_connector_rassembly(
    assembly: Assembly,
    connector_id: str,
    source_component_id: str,
    source_connector_id: str,
    name: str | None = None,
    offset: Placement | None = None,
) -> Assembly
```

The `offset` composes after the forwarded source connector. It supports useful
interfaces such as a connector at a bearing shoulder offset from a ring axis.

Keep nested connector refs as a later extension:

```python
make_nested_connector_ref_rconnectorref(
    component_path: tuple[str, ...],
    connector_id: str,
) -> ConnectorRef
```

This should not be part of the first implementation, because it requires deeper
solver changes. First expose subassembly interface connectors explicitly.

## Standard Library Usage

`make_ball_bearing_rassembly(...)` should expose assembly-level public interface
connectors in addition to its internal ring connectors.

Expected bearing assembly interface:

```python
bearing.connector_ids() == (..., "inner_axis", "outer_axis")
```

Factory behavior:

```python
bearing = forward_connector_rassembly(
    assembly=bearing,
    connector_id="inner_axis",
    source_component_id="inner_ring",
    source_connector_id="axis",
    name="Inner ring shaft axis",
)
bearing = forward_connector_rassembly(
    assembly=bearing,
    connector_id="outer_axis",
    source_component_id="outer_ring",
    source_connector_id="axis",
    name="Outer ring housing axis",
)
```

Parent assembly usage:

```python
assembly = add_fixed_constraint_rassembly(
    assembly=assembly,
    constraint_id="input_bearing_inner_to_input_shaft",
    connector_a=make_connector_ref_rconnectorref(
        component_id="input_bearing",
        connector_id="inner_axis",
    ),
    connector_b=make_connector_ref_rconnectorref(
        component_id="input_shaft",
        connector_id="bearing_axis",
    ),
)
```

## Solver Behavior

Connector resolution must become anchor-aware.

Geometry connector resolution:

```text
connector_frame = placement_from_geometry_ref(connector.geometry_ref)
```

Placement connector resolution:

```text
connector_frame = connector.anchor.placement
```

Forwarded connector resolution inside an assembly definition:

```text
source_component = owning_assembly.get_component(source_component_id)
source_connector = source_component.item.get_connector(source_connector_id)
source_frame = source_component.placement * resolve_connector(source_connector)
connector_frame = source_frame * optional_offset
```

Parent assembly world frame resolution remains:

```text
world_frame = parent_component.placement * component_connector_frame
```

Important solver rule:

- A forwarded connector is an interface datum of the subassembly component.
- A parent-level constraint that references a forwarded connector constrains the
  subassembly component placement, not the internal child placement.
- The first implementation should not push parent-level motion into internal
  child components.
- Internal degrees of freedom remain solved by constraints inside the subassembly.
- If parent-level control of an internal child is required later, that is a
  nested constraint solving feature and should be designed separately.

This rule is sufficient for bearing placement and most mechanical interface
constraints: a bearing's public `inner_axis` and `outer_axis` can locate the
subassembly as an interface object. If an application needs independent inner
and outer ring motion at the root assembly level, it should either work inside
the bearing assembly or explicitly expand the bearing into the parent.

## Model JSON and Replay Behavior

Connector serialization should include the anchor kind.

Example forwarded connector JSON:

```json
{
  "connector_id": "inner_axis",
  "name": "Inner ring shaft axis",
  "anchor": {
    "anchor_kind": "forwarded",
    "source_component_id": "inner_ring",
    "source_connector_id": "axis",
    "offset": null
  }
}
```

Compatibility rule:

- Existing connector JSON with `geometry_ref` is treated as `anchor_kind =
  "geometry"` during import.
- New exports should use the explicit anchor envelope.

Replay requirements:

- `make_placement_connector_rconnector(...)` is graph-recorded and replayable.
- `forward_connector_rassembly(...)` is graph-recorded and replayable.
- Replay validates that the source component and source connector exist.
- Replay preserves connector IDs exactly.
- Replay fails explicitly if a forwarded connector points to a missing internal
  component or missing source connector.

## FreeCAD Translator Behavior

FreeCAD export should materialize public connectors as datum coordinate systems
or local coordinate system objects on the generated Part or Assembly container.

Geometry connector behavior:

- Existing behavior may continue to resolve a face/edge/vertex selector and
  create a datum from that geometry.
- Where possible, generated datum placements should be cached in product values
  so constraints can reference frames rather than re-select topology.

Placement connector behavior:

- Emit a FreeCAD datum coordinate system directly from the stored placement.
- No BREP selector is needed.

Forwarded connector behavior:

- Resolve the source component link placement in the generated assembly.
- Resolve the source component connector's local datum placement.
- Compose those placements in the assembly container coordinate system.
- Emit a public datum on the assembly container with the forwarded connector ID.
- Use that public datum for parent-level links and constraints.

FreeCAD naming convention:

```text
connector_id = "inner_axis"
FreeCAD object label = "connector.inner_axis"
Internal variable key = connectors["inner_axis"]
```

Translator constraints:

- Parent assembly constraints should reference the public datum on the linked
  subassembly, not a private datum inside the linked subassembly body.
- If FreeCAD AssemblyLink cannot expose a subassembly datum directly, the
  translator should create a proxy datum next to the AssemblyLink using the
  composed placement.
- The translator should avoid edge selector resolution for placement or forwarded
  connectors.

## Validation and Error Handling

Validation rules:

- `connector_id` must be unique within a `Part` or `Assembly`.
- A forwarded connector source component must exist in the owning assembly.
- A forwarded connector source connector must exist on the source item.
- Forwarding cycles are rejected.
- Offsets must be valid right-handed placements.
- A connector cannot forward to itself.

Error examples:

```text
forwarded connector 'inner_axis' references missing component 'inner_ring'
forwarded connector 'outer_axis' references missing connector 'axis' on component 'outer_ring'
forwarded connector cycle detected: a -> b -> a
```

## Implementation Phases

Phase 1: data model and replay.

- Add `ConnectorAnchor` or equivalent internal representation.
- Keep reading legacy `geometry_ref` connector payloads.
- Add `make_placement_connector_rconnector(...)`.
- Add `forward_connector_rassembly(...)`.
- Add serializer and replay support.
- Add unit tests for missing source, duplicate IDs, and replay.

Phase 2: solver support.

- Update connector placement resolution to support geometry, placement, and
  forwarded anchors.
- Update constraint residual measurement to use anchor-aware connector frames.
- Add tests for fixed and revolute constraints using forwarded connectors.
- Add tests for nested assembly component placement composition.

Phase 3: FreeCAD translator support.

- Emit placement connectors as FreeCAD datums without topology lookup.
- Emit forwarded connectors as public assembly datums or proxy datums.
- Update generated script product values to include connector datum placements.
- Add translator tests that inspect generated script content.
- Add an integration example that produces `.FCStd` with a bearing subassembly
  exposing `inner_axis` and `outer_axis`.

Phase 4: standard-library adoption.

- Update `make_ball_bearing_rassembly(...)` to expose `inner_axis` and
  `outer_axis` through forwarding.
- Update examples to bind bearing inner and outer interfaces at parent assembly
  level.
- Update generated API and stdlib docs.

## Acceptance Criteria

SDK acceptance:

- A user can create a placement-only connector and use it in an assembly
  constraint.
- A user can forward an internal component connector to an assembly-level public
  connector.
- `connector_ids()` on an assembly includes forwarded connectors.
- `get_connector(...)` resolves forwarded connectors to the expected local
  placement.
- `export_model_json(...)` records forwarded connectors.
- `replay_model_json(...)` rebuilds forwarded connectors and constraints.

Solver acceptance:

- Fixed constraints between a part connector and a forwarded subassembly
  connector solve with zero residual within tolerance.
- Revolute constraints between a shaft axis and a forwarded bearing inner axis
  solve with zero translation residual and acceptable angular residual.
- Grounding a subassembly component and constraining to its forwarded connector
  behaves the same as constraining to an equivalent placement connector.
- Invalid forwarded references fail with clear errors.

FreeCAD acceptance:

- `.FCStd` export contains visible datum objects for placement connectors.
- `.FCStd` export contains visible public datum objects for forwarded assembly
  connectors.
- A parent assembly link can reference a subassembly's forwarded datum or proxy
  datum without reselecting private BREP edges.
- The generated FreeCAD script does not need edge selector matching for forwarded
  connectors.
- A bearing example exports to `.FCStd` with `inner_axis` and `outer_axis` present
  on each bearing subassembly instance.

Reducer example acceptance:

- The compact two-stage reducer can place nine bearing instances.
- Each bearing exposes `inner_axis` and `outer_axis` to the parent reducer
  assembly.
- Input, intermediate, output, and planet bearing inner axes can be constrained to
  shafts or pins.
- Bearing outer axes can be constrained to housings, carriers, or gear bores as
  appropriate.
- The reducer still exports model JSON, replays, writes STEP, and writes FCStd.

## Non-Goals For The First Implementation

- Full arbitrary-depth connector refs in public APIs.
- Parent-level constraints that directly solve internal child component motion.
- Physical contact or bearing preload simulation.
- Automatic inference of bearing interfaces from geometry alone.
- Replacing the existing geometry connector API.

## Open Questions

- Should placement-only connectors be allowed on `Part` values, `Assembly` values,
  or both from the first release?
- Should forwarded connector offsets be stored as raw placement payloads or as
  graph-recorded `Placement` inputs?
- Should the FreeCAD translator emit connector datums even when there are no
  constraints referencing them?
- Should standard-library factories expose interface connectors by default, or
  behind an option such as `expose_interface_connectors=True`?
