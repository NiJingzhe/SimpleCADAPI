# forward_connector_rassembly

## API Definition

```python
def forward_connector_rassembly(assembly: Assembly, connector_id: str, source_component_id: str, source_connector_id: str, name: Optional[str] = None, offset: Optional[Placement] = None) -> Assembly
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import forward_connector_rassembly`

## Description

Expose an internal component connector as an assembly-level connector.

The forwarded connector resolves to `source_component.placement *
source_connector.placement`, followed by the optional `offset` placement.
Parent assemblies can constrain to the subassembly's public connector
without depending on its private component structure.
