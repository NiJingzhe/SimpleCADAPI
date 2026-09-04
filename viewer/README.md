# SimpleCAD Product Viewer

This browser-only viewer opens canonical `.scadpkg` product packages (package
schema 3.0) without importing SimpleCAD, Python, or OpenCascade. The loader
validates `package.json`, the exact member closure (`definitions/`,
`occurrences/root.json`, `blobs/`, `projections/scene/scene.json`), and the
embedded evaluated scene before parsing GLB or entity assets. It rejects older
package schemas, standalone Scene ZIPs, and any package with missing, extra,
length-mismatched, or hash-mismatched members. Product definition ZIPs and
feature-graph archives are integrity-checked as package blobs but never
re-packed, because the viewer renders exclusively from the scene projection.

## Run

```bash
npm install
npm run dev
```

Open `http://localhost:5173/`, click **Open .scadpkg**, and select a package
written directly by the functional capture API:

```python
scad.capture(result, "out/product.scadpkg")
```

The same file can be dropped directly into the viewport.

The file picker accepts local `.scadpkg` product packages only. The viewer does
not load packages from URL query parameters or require a built-in case registry.

## Inspecting A Product

The **Components** tab shows the evaluated occurrence hierarchy. Select an
occurrence to inspect its definition, visibility, and evaluated body data. The
visibility control on each row hides or shows that occurrence.

The **Features** tab federates the immutable feature DAGs embedded by every part
and nested assembly definition. Selecting a feature shows its operation,
definition-local identity, inputs, outputs, parameters, source spans, and linked
geometry. Connector and joint selections resolve through the package indexes to
the exact producing feature when that evidence exists.

The source panel lists the content-addressed source snapshots embedded by the
definition closure. Selecting a mapped feature opens the exact source asset,
scrolls to its recorded line range, and highlights that range without reading
files from the local machine.

Select components, solids, faces, edges, or vertices in the viewport to inspect
evaluated geometry and measurements. Geometry selections link back to the
feature DAG through stable definition, node, output-slot, and topology evidence.
