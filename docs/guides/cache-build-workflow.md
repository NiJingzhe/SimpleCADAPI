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

`@scad.part` and `@scad.assemble` are top-level product boundaries and cannot be
nested inside an active `GraphSession`. Continue to use `@scad.model` plus
`@scad.requires_session` for a replayable geometry flow that is not a durable
part/assembly definition.


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
format. Export `PartDefinition` or `AssemblyDefinition` artifacts instead.
