# Topology QL Design

## Goal

Design a query language that can serve all of the following roles at once:

1. Select sub-topology (`Vertex`, `Edge`, `Wire`, `Face`, `Solid`) during modeling
2. Be serialized into graph JSON and replayed in another script
3. Remain understandable enough for GUI / low-code presentation
4. Be strict enough to detect ambiguous or unstable selections

The key design constraint is that this is **not** just an in-memory filter API.
It must be a **canonical selection representation** for graph replay.


## Core Principle

Runtime object references are useful, but they are not a durable source of truth.

The durable source of truth for selection must be a declarative, serializable,
graph-aware `SelectionSpec`.

The user may still pass object lists or query helpers ergonomically, but the
system should normalize all of them into the same canonical selection form.


## What QL Must Select

QL must operate over a specific topology universe:

- `vertex`
- `edge`
- `wire`
- `face`
- `solid`

Each query is evaluated inside a **scope**, not globally. The minimum stable
scope is a graph node output:

- `source_node_id`
- `source_output_slot`

Without scope, replay is underspecified.


## SelectionSpec

The canonical serialized form should be `SelectionSpec`.

```json
{
  "source_node_id": "node_17",
  "source_output_slot": 0,
  "target_kind": "edge",
  "query": {
    "all": [
      {"curve_type": "CIRCLE"},
      {"center_compare": {"axis": "z", "op": "<=", "value": 0.0}}
    ]
  },
  "order_by": [
    {"center_axis": "z", "desc": false},
    {"metric": "length", "desc": true}
  ],
  "limit": 1,
  "cardinality": {"exactly": 1},
  "fallback": {
    "topo_refs": [...],
    "indices": [0],
    "selector_hints": [...]
  }
}
```

### Why this shape

- `query` answers: *what semantic thing are we selecting?*
- `order_by` answers: *if multiple things match, how are they ranked?*
- `limit` answers: *how many do we take?*
- `cardinality` answers: *what count is acceptable?*
- `fallback` answers: *what do we try when semantic matching is not enough?*


## QL Has Three Layers

### 1. Predicate layer

Boolean filters over topology objects.

Examples:

- `tag("face.top")`
- `meta("track.event", "==", "generated")`
- `curve_type("circle")`
- `surface_type("plane")`
- `metric("length", ">", 5.0)`
- `center_compare("z", "<", 0.0)`
- `normal_axis("z", ">", 0.9)`

These must be serializable into an AST.

### 2. Selection layer

Defines target kind, filter, ordering, limit, and cardinality.

Examples:

- `Q.edges().where(...).order_by(...).take(1).exactly(1)`
- `Q.faces().where(...).take(4).exactly(4)`

This is what should become `SelectionSpec` in graph JSON.

### 3. Graph layer

Connects selection to a specific graph output.

Examples:

- "edges on the output of the node that created the thread body"
- "faces on the result of the last cut"

The GUI must expose this layer clearly.


## Predicate Families

### A. Semantic predicates

These rely on tags and metadata and are the most stable across rebuilds.

- `tag(pattern)`
- `meta(path, op, value)`
- `op(name, event="*")`
- `origin(role)`
- `role(name)`

These should remain the backbone of stable replay whenever possible.

### B. Geometric type predicates

These identify analytic geometry classes.

- `curve_type("line" | "circle" | "ellipse" | "bspline" | ...)`
- `surface_type("plane" | "cylinder" | "sphere" | "cone" | "torus" | ... )`

These are necessary for things like selecting cylindrical hole walls or circular
bottom edges.

### C. Metric predicates

These compare numeric geometric properties.

- `metric("length", op, value)`
- `metric("area", op, value)`
- `metric("volume", op, value)`
- `metric("radius", op, value)`
- `metric("edge_count", op, value)`

These should support toleranced comparisons eventually.

### D. Positional predicates

These use centers, coordinates, normals, or bounding boxes.

- `center_compare(axis, op, value)`
- `center_between(axis, min, max)`
- `normal_axis(axis, op, value)`
- `bbox_compare(bound, axis, op, value)`

These are essential for "top face", "bottom edge", "left-most face" style
queries.

### E. Structural predicates

These reason about topology relationships.

- `is_outer_wire()`
- `is_inner_wire()`
- `wire_closed(True|False)`
- `child_of(tag/meta/query)`
- `parent_kind("face")`

These are important for topology-aware selections beyond raw geometry.


## Ordering Is Not Optional

Filtering is not enough. We need deterministic ordering because replay cannot
trust OCC's iteration order.

Required ordering primitives:

- `order_by(center_axis("z"), desc=False)`
- `order_by(metric_value("length"), desc=True)`
- lexicographic multi-key ordering

Ordering is what turns:

> circular bottom edges

into:

> the lowest circular edge, then the largest one, take exactly 1


## Cardinality Is Part of the Query

Queries must say not just what to select, but how many are acceptable.

Supported forms should include:

- `exactly(n)`
- `at_least(n)`
- `at_most(n)`

Why this matters:

- If replay matches 0 instead of 1, that is usually a hard failure.
- If replay matches 4 instead of 1, that usually indicates ambiguity.
- GUI should display cardinality expectations explicitly.


## Fallback Strategy Chain

QL is the canonical intent, but replay still needs practical fallback.

Proposed resolution order:

1. Evaluate `SelectionSpec.query` against the replayed scope
2. Apply `order_by`, `limit`, `cardinality`
3. If this fails, try stored `topo_ref`
4. If this fails, try stored `indices`
5. If this fails, use `selector_hints`

Important: QL should be the **first-class** path, not a late fallback.


## What QL Should Not Try To Be

### Not arbitrary Python

This is bad for replay:

```python
Q.edges().where(lambda e: e.get_length() > 5)
```

Reason: lambda is not portable or serializable.

### Not kernel-internal topo identity

This is not stable enough to be the primary selection language:

- raw OCC face ids
- `HashCode`
- enumeration order

These are valid fallback channels, not canonical query semantics.


## Where Current QL Sits

Current implementation already supports a first step toward this design:

- serializable predicates for tag/meta/curve_type/surface_type
- serializable ordering via `center_axis`
- serializable selectors via `ShapeSelector`
- replay path for `fillet/chamfer/shell` using `selection_query`

What is still missing:

- metric predicates
- richer positional predicates
- explicit `SelectionSpec` schema with source node scope
- multi-key ordering
- formal cardinality beyond `exactly`
- structural predicates


## Why This Matters For Evolve

`evolve` is mostly operation composition, so it is a good fit for graph replay.

The hard part is hidden topology selection like:

```python
edges = solid.get_edges()
bottom_edge = edges[:1]
```

This should become:

```python
Q.edges()
 .where(Q.curve_type("circle"))
 .order_by(Q.center_axis("z"))
 .take(1)
 .exactly(1)
```

This is the exact reason QL should become the canonical selection path.


## Incremental Migration Plan

### Phase 1

Already started:

- serializable selectors
- replay for `fillet/chamfer/shell`
- first `evolve` migration (`make_threaded_rod_rsolid` bottom chamfer)

### Phase 2

Add geometry metrics and richer positional predicates:

- `metric(name, op, value)`
- `center_compare(axis, op, value)`
- `normal_axis(axis, op, value)`

### Phase 3

Introduce formal `SelectionSpec` in graph JSON:

- add source node/output scope
- make it the canonical serialized selection object
- keep topo refs / indices / hints as fallback section

### Phase 4

Migrate more hidden selections in `evolve` and other APIs to QL.

### Phase 5

Expose GUI-oriented rendering of selections:

- label
- source scope
- target kind
- cardinality
- human-readable summary


## Practical Rule

If a selection must survive serialization and replay, it should ultimately be
expressible as QL.

Passing concrete objects should remain ergonomic at the API boundary, but the
system should normalize them into `SelectionSpec` internally whenever possible.
