# Shell

`Shell` is not part of the stable SimpleCADAPI 2.0 beta public wrapper surface.

Use `Face` for bounded surfaces and `Solid` for closed 3D bodies. For thin-walled parts, use the public feature operation:

```python
shelled = shell_rsolid(solid, faces_to_remove, thickness)
```

See [`shell_rsolid`](../api/shell_rsolid.md) for the stable public operation.
