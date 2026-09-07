# Persistent Cache and Product Build Workflow

SimpleCADAPI uses one crash-safe content-addressed store for whole-part builds
and incremental assembly solves. The default root is `.simplecad/cache`;
`.simplecad/state` stores the latest part and assembly interface snapshots used
for incremental invalidation.

## Product boundaries

Use `@scad.part` for one physical, single-solid part. It returns a
`PartBuildResult` with the runtime `Part`, a durable `PartDefinition`, graph and
session state, replay payloads, interface differences, and a `CacheReport`. The
build key includes the definition ID and revision, normalized arguments, builder
source, declared file inputs, generator/ABI profile, and tolerance profile.

```python
import simplecadapi as scad


@scad.part(id="mounting_plate", revision="1.0.0", cache="auto")
def build_plate(width: float = 30.0) -> scad.Part:
    body = scad.make_box_rsolid(width=width, height=20.0, depth=3.0)
    return scad.make_part_rpart(part_id="mounting_plate", body=body)


cold = build_plate()
warm = build_plate()
print(cold.cache_report.hit, warm.cache_report.hit)
```

Declare every non-Python input with `scad.file_input(...)`; undeclared file
reads cannot participate in the build key. In `read_only` or `read_write` mode,
repeated calls to the same decorated builder and build key reuse the same runtime
PRT in memory with zero cache I/O. Concurrent same-key calls share one build.

A newly decorated builder or later process restores unchanged PRTs from the
durable part bundle. Restore validates the closed cache bundle, exact solid,
topology snapshot, durable definition, and interface hashes, then creates fresh
runtime objects and graph provenance. Corrupt bundles are quarantined and
rebuilt. `off` and `refresh` always execute the builder.

Use `@scad.assemble` for an assembly whose external part or nested assembly
definitions are explicit. Repeated instances reference one immutable
definition. The incremental solver invalidates only components reached through
changed geometry, connector, binding, material, or nested public-connector
interfaces; cached placements still pass residual verification before reuse.

```python
@scad.assemble(id="fixture", definitions=(warm,), cache="auto")
def build_fixture() -> scad.Assembly:
    assembly = scad.make_assembly_rassembly(assembly_id="fixture")
    return scad.add_component_rassembly(
        assembly=assembly,
        item=warm.value,
        component_id="plate",
        placement=scad.identity_placement_rplacement(),
    )


fixture = build_fixture()
print(fixture.solve_report.component_hits, fixture.solve_report.component_misses)
```

`@scad.part` and `@scad.assemble` are top-level product boundaries and each owns
its definition-local `GraphSession`; they cannot be nested inside another active
session. Use an explicit `GraphSession` for lower-level replayable geometry that
is not a durable part or assembly definition.


## Policy

Policy precedence is explicit decorator argument, environment variables,
`[tool.simplecadapi.cache]` in the project `pyproject.toml`, then defaults.
Relative roots resolve against the project root.

```toml
[tool.simplecadapi.cache]
mode = "read_write"            # off | read_only | read_write | refresh
root = ".simplecad/cache"
verify_reads = true
quarantine_corrupt = true
lock_timeout_seconds = 30
stale_lock_seconds = 300
```

Environment overrides are `SIMPLECAD_CACHE_MODE`, `SIMPLECAD_CACHE_DIR`,
`SIMPLECAD_CACHE_VERIFY_READS`, `SIMPLECAD_CACHE_QUARANTINE_CORRUPT`,
`SIMPLECAD_CACHE_LOCK_TIMEOUT`, and `SIMPLECAD_CACHE_STALE_LOCK`.

- `off`: bypass reads and writes.
- `read_only`: accept valid hits but never populate misses.
- `read_write`: read valid hits and atomically populate misses.
- `refresh`: recompute and replace entries without reading existing values.

## Diagnostics and maintenance

`simplecad-cache` prints one stable JSON object. `status`, `verify`, and the
default `prune` mode are read-only. Explicit mutation is required for repair,
pruning, and clearing.

```bash
simplecad-cache status
simplecad-cache status --namespace part
simplecad-cache verify
simplecad-cache verify --repair
simplecad-cache prune
simplecad-cache prune --apply
simplecad-cache clear --namespace part --yes
```

`verify` always checks record schema/path, object presence, byte length, and
SHA-256, even when runtime `verify_reads` is disabled. `--repair` quarantines
invalid records and objects. `prune` reports unreferenced canonical objects;
`--apply` quarantines them. Namespace clearing preserves objects referenced by
other namespaces. Full clearing requires `--yes` and removes the cache root.

Writers use per-key atomic locks, stale-lock recovery, atomic replacement, and
content-addressed object deduplication. Treat `.simplecad` as generated state:
do not commit it and do not use its internal files as a public interchange
format.

## Product package export

`PartBuildResult` and `AssemblyBuildResult` are captured and written as one
canonical product package by a single API call:

```python
scad.capture(warm, "out/part.scadpkg")
scad.capture(fixture, "out/assembly.scadpkg")

root = scad.load_product_package("out/assembly.scadpkg")
rebuilt = scad.materialize_definition(root)
```

Use `build_product_package(...)`, `encode_product_package(...)`,
`read_product_package(...)`, and `load_product_package(...)` only for explicit
in-memory package handling. `validate_product_package(...)` verifies every object
hash and size, the complete recursive definition graph, cycle/depth limits, and
rejects missing or unreferenced objects. Use `export_part_definition(...)` or
`export_assembly_definition(...)` only for low-level definition exchange or
inspection; neither is the product delivery format.

## Downstream CAD and mesh targets

Keep `.scadpkg` as the canonical SimpleCAD delivery artifact. Choose a
downstream target from the consumer contract:

| Target | Use when | Preserved contract | Boundary |
| --- | --- | --- | --- |
| `.scadpkg` | Rebuild, replay, cache, or further SimpleCAD editing is required | Complete durable definition closure, feature graphs, source snapshots, topology, connectors, constraints, and materials | SimpleCAD-specific archive |
| `.FCStd` | A FreeCAD user needs an editable native document | Definition-owned, dependency-first native feature graphs; final body links; repeated instances; nested assemblies; names; solved placements; materials; connectors; constraints; grounding; revision; and content hashes | Requires FreeCADCmd/FreeCAD |
| AP242 `.step` | Neutral CAD exchange or downstream OpenCASCADE tooling is required | Evaluated BREP, product hierarchy, shared definitions, occurrence names/placements, materials, colors, density, and named SimpleCAD property payloads | Canonical feature history is not reconstructed as AP242 features |
| Triangle `.obj` | Surface inspection or DCC exchange needs an indexed mesh | Direct OpenCASCADE tessellation of evaluated BREP with shared vertices and oriented triangles | Evaluated surface mesh only; no CAD hierarchy, feature semantics, quads, or materials |
| Binary `.stl` | Additive manufacturing or triangle-only consumers | The same direct OpenCASCADE BREP triangles | Facet soup only; no shared vertices, CAD hierarchy, feature semantics, or materials |

```python
package_path = assembly_package.artifact_paths["product"]

fcstd_path = scad.translator.freecad_translator.translate_product_package_to_fcstd(
    package_path,
    "out/product.FCStd",
)
step_report = scad.exporter.export_product_package_to_step(
    package_path,
    "out/product.step",
)
stl_report = scad.exporter.export_product_package_to_stl(
    package_path,
    "out/product.stl",
)
obj_report = scad.exporter.export_product_package_to_obj(
    package_path,
    "out/product.obj",
)
print(step_report.definition_ids, step_report.occurrence_count)
print(stl_report.solid_count, stl_report.triangle_count)
print(obj_report.vertex_count, obj_report.triangle_count)
```

STL and OBJ use the same direct OpenCASCADE tessellation and parameters. Set
`linear_deflection` to the maximum chordal deviation in product units and
`angular_deflection_degrees` to the curved-surface angular limit. Both formats
contain oriented triangles; OBJ preserves shared vertex indices while binary STL
stores each facet independently. No remeshing or optional dependency is involved.

AP242 definition and occurrence metadata is stored in one standard
`PROPERTY_DEFINITION_REPRESENTATION`. Its named
`DESCRIPTIVE_REPRESENTATION_ITEM` records use
`SimpleCAD:definition:<kind>:<definition_id>` and
`SimpleCAD:occurrence:<parent_definition_id>:<component_id>`. Each description
is canonical sorted JSON containing durable IDs, revision, content hash,
connectors, constraints, grounding, name, and solved placement.
`ProductSTEPExportReport` reports the schema, definition IDs, occurrence
count, material IDs, metadata item count, and explicit limitations.

For tetrahedral meshing, run the split example directly in dependency order:
`model.py` captures `.scadpkg`, `export_step.py` exports AP242 STEP, and
`export_fem_mesh.py` imports that STEP with Gmsh's OpenCASCADE kernel. The FEM
stage rejects imports with no 3D volumes, generates a dimension-3 mesh, writes
`.msh`, and always finalizes Gmsh. Install and invoke the optional dependency
with `uv run --extra gmsh python
examples/ap242_gmsh_volume_mesh/export_fem_mesh.py`; Gmsh is never imported
by the core SDK or product exporters.
