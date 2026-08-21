# Public Connector Refactor

Status: complete

## Decision

An Assembly public connector is an interface declaration, not a second `Connector` object.

Users create the real connector on the direct child component first, then mark that connector as public:

```python
assembly = scad.set_public_connector_rassembly(
    assembly,
    public_connector_id="output_axis",
    source_component_id="rotor",
    source_connector_id="axis",
)
```

`set_public_connector_rassembly`:

- does not create or clone a `Connector`;
- does not accept an offset or geometry;
- does not move the source component;
- records only the public interface name and the direct-child source reference;
- requires the source component to already exist and the source connector to already exist;
- requires public IDs to be unique within the Assembly.

The source is a direct child component. A direct child Assembly may be used only through a connector that it exposes publicly; the public boundary remains one level at a time.

## Runtime contract

`Assembly` does not own a connector collection. Public declarations live in `Assembly.public_connectors` as immutable `PublicConnectorRef` values, while concrete `Connector` values remain owned by leaf `Part` instances.

A public reference contains:

```text
public_connector_id
source_component_id
source_connector_id
name (optional)
```

No offset is stored. The source connector owns its complete frame.

Resolving a parent constraint against a child Assembly public connector returns the real source connector plus its composed frame. The frame includes each direct component placement encountered while crossing nested public boundaries.

## Durable package contract

`AssemblyDefinition` stores public connector declarations under `public_connectors`. Each declaration stores the public ID, direct-child source reference, optional name, and a resolved frame snapshot used for validation and standalone consumers. It does not use `anchor_kind="forwarded"`, `forwarded_from`, or an offset.

The declaration and source connector are hashed as part of the Assembly interface. Changing the public name, source component, source connector, or resolved frame changes the Assembly interface hash and invalidates dependent builds.

## Solver contract

The solver resolves a public connector reference to the actual leaf connector and its world frame. Public declarations do not create a new rigid body, motion edge, or constraint. A public connector cannot make an internal component movable merely because a parent constraint references it; movement follows the existing assembly constraint graph.

This deliberately removes the old special case that descended through forwarded connectors to mutate a nested leaf placement. Nested mechanisms must expose and solve their own constraints before a parent consumes their public interface.

## Scene and exporters

Scene records distinguish connector ownership from public declarations. A public record references the source connector snapshot and carries the resolved frame for validation. Exporters use the source connector for semantic ownership and the resolved public frame for sites/joint consumers.

MJCF must not infer a joint from public exposure. Public declarations only identify externally visible sites/endpoints. Hinge/prismatic edges come from explicit assembly constraints.

## Translator and replay

The replay operation is `make_set_public_connector_rassembly`. Its parameters contain the public ID, source component ID, source connector ID, and optional name. There is no placement input and no offset branch.

## Migration policy

This is a clean cutover on the branch. Remove `forward_connector_rassembly`, the forwarded anchor kind, forwarded offsets, and translator/replay branches after all callers and durable schemas migrate. Do not leave aliases or deprecated compatibility paths.

## Progress

- [x] Confirm public semantics: declaration, no clone, no offset, direct child source.
- [x] Replace runtime Assembly public connector storage and resolution.
- [x] Migrate durable AssemblyDefinition and schemas.
- [x] Migrate solver and product-package construction.
- [x] Migrate scene compiler/validation and exporters.
- [x] Migrate serializer/replay and translators.
- [x] Migrate callers/tests and run end-to-end verification.
