Tagging Refactor Plan (Naming + Propagation + Anchor Semantics)

Goals
- Define a strict, query-friendly tag naming scheme for QL.
- Make tag propagation explicit, predictable, and consistent across topology levels.
- Align tag semantics with constraint/assembly anchors.
- Move all numeric geometry data into metadata/geo data (no numbers in tags).

Non-Goals (Phase 1)
- Persistent topological IDs across boolean ops and remeshing.
- Automatic recovery of face/edge tags after arbitrary topology changes.
- Full QL implementation (this plan only prepares the data model).

1) Tag Naming Scheme

Format
- Lowercase ASCII only.
- Dot-separated segments: segment(.segment)*
- Segment grammar: [a-z][a-z0-9_-]*
- Forbidden: whitespace, colon (:), slash (/), uppercase.

Rationale
- Dot segments allow prefix queries (QL) and structured namespaces.
- No colon because anchor syntax uses face:<tag>.

Examples
- geom.primitive.box
- face.top
- edge.circular
- feature.extrude.start_face
- role.mounting_surface
- anchor.datum.primary
- group.fasteners
- state.debug

2) Tag Namespaces (Reserved Prefixes)

Core namespaces (stable semantics)
- geom.*: geometry category/type (primitive or derived)
- face.* / edge.* / wire.* / vertex.* / solid.*: topology-level semantics
- role.*: stable semantic role (preferred for anchors and QL)
- anchor.*: explicit anchor naming (aliasable from role.*)
- group.*: grouping and selection convenience

Process/ephemeral namespaces
- feature.*: derived from operations (extrude, loft, sweep, boolean)
- state.*: debug/test/temporary flags (not for anchors)
- legacy.*: compatibility aliases during migration

Multiple namespaces on one object
- Yes, a single object can carry multiple tags from different namespaces.
- Tags are orthogonal: e.g., a face can be both geom.primitive.box and role.mounting_surface.
- Avoid redundant tags that encode the same meaning across namespaces.
- Anchor resolution uses a defined priority (role > anchor > face/edge/wire > legacy).

3) Propagation Rules

Principles
- Propagation is opt-in and prefix-based.
- Only stable semantic tags should propagate by default.
- Propagation should be directional (parent -> children) and explicit.

Default propagation policy by prefix
- role.*: propagate down (Solid -> Face -> Wire -> Edge -> Vertex)
- anchor.*: propagate down (same as role.*)
- group.*: propagate down (same as role.*)
- geom.*: propagate down to Face/Wire/Edge (optional; toggleable)
- face.* / edge.* / wire.* / vertex.*: do NOT propagate (object-specific)
- feature.*: do NOT propagate by default
- state.*: never propagate

Implementation sketch
- Introduce a TagPolicy registry keyed by prefix.
- Add propagate parameter to set_tag (none | down | custom).
- Provide helper: apply_tag(shape, tag, propagate=None).
- Propagation should be implemented in core (TaggedMixin) and reused in ops.

4) Anchor Semantics (Constraint Integration)

Anchor naming goals
- Anchor selection should be stable and semantic.
- Anchor names should be directly queryable by QL.
- Existing anchor syntax (face:<tag>) should remain valid.

Proposed rules
- Use role.* as the primary semantic source for anchors.
- For standard primitives, define canonical face tags:
  - face.top / face.bottom / face.left / face.right / face.front / face.back
  - face.side (cylinder/cone), face.surface (sphere)
- For assembly anchors, resolve tag by priority:
  1) role.<tag>
  2) anchor.<tag>
  3) face.<tag> (or edge.<tag>, wire.<tag>)
  4) legacy.<tag> and historical tags (top, bottom, side, surface)

Example
- Face tag: role.mounting_surface
- Anchor usage: face:mounting_surface
- Resolver maps to role.mounting_surface (or anchor.mounting_surface)

5) Geometry Data in Metadata/Geo Data

Policy
- No numeric or dimensional data in tags.
- All geometry facts go into metadata under a reserved key.

Proposed schema
- metadata["geo"]: dict with normalized keys
  - type: "box" | "cylinder" | "sphere" | ...
  - size: {x, y, z} or {radius, height}
  - center: (x, y, z)
  - axis: (x, y, z)
  - bbox: {min, max, center, size}

Example (box)
- tags: geom.primitive.box, role.container
- metadata["geo"]:
  {"type":"box","size":{"x":4,"y":3,"z":2},"center":(0,0,0)}

6) Migration Plan (Incremental)

Phase A: Naming and aliasing
- Add TagPolicy registry and prefix normalization utilities.
- Update anchor resolver to try role/anchor/face prefixes + legacy tags.
- Start emitting role/face tags in auto_tag_faces with legacy aliases.

Phase B: Propagation
- Implement propagation helpers in TaggedMixin (downward only).
- Update auto_tag_faces to call propagation hooks.
- Add explicit propagation to key ops (extrude/loft/sweep/mirror).

Phase C: Geo data
- Replace numeric tag strings with metadata["geo"] in primitives.
- Deprecate tags like "size: 2x3x4" and "bottom center: ...".

Phase D: Query readiness
- Update docs and tests to use role/anchor semantics.
- Provide QL examples for tag prefix queries and geo metadata queries.

7) Compatibility Notes
- Keep legacy tags during migration (add legacy.* aliases).
- Provide a single normalization helper for tag lookup and anchor selection.
- Document any tag renames in release notes and update tests.

Open Questions
- Should geom.* propagate by default or remain opt-in?
- Do we need a separate geo_data attribute instead of metadata["geo"]?
- Should anchors prefer role.* over face.* even when both exist?
- How far should propagation go for Wire/Edge derived from new topology?
