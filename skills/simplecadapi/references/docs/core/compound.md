# Compound

`Compound` is reserved documentation for collection-style geometry workflows.

SimpleCADAPI 2.0 beta focuses the stable public geometry wrapper surface on:

- `Vertex`
- `Edge`
- `Wire`
- `Face`
- `Solid`

For multi-body workflows, prefer Python sequences of `Solid` objects plus export helpers such as `export_step([...], path)` or assembly APIs such as `make_assembly_rassembly(...)`.
