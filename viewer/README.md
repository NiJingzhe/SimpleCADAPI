# SimpleCAD Scene Viewer

This is a browser-only viewer for exported `Scene Schema 1.0` packages. It
does not import SimpleCAD, Python, or OpenCascade. The loader reads the
canonical `.scene.zip`, parses `scene.json`, and loads the referenced GLB and
entity sidecar assets. When present, it also loads `model/model.json` and the
manifest-declared Python files under `sources/`. ZIP resource limits and every
referenced member's exact byte length and SHA-256 are checked before scene
assets are parsed.

## Run

```bash
npm install
npm run prepare:example
npm run dev
```

Open `http://localhost:5173/`, click **Open .scene.zip**, and select the package
generated at `examples/out/hydraulic_rod_assembly/hydraulic_rod_assembly.scene.zip`.
The same file can be dropped directly into the viewport.

The file picker accepts any local `.scene.zip` package. The viewer does not
load scenes from URL query parameters or require a built-in case registry.

## Inspecting A Model

The left **ASSEMBLY** tab shows the evaluated occurrence hierarchy. Click an
occurrence to inspect its definition, visibility, and evaluated body data. Use
the visibility control on a row to hide or show that occurrence.

The **FEATURES** tab shows the embedded replayable operation tree from
`model/model.json`. Select an operation to inspect its canonical operation name,
category, inputs, output count, parameters, and summary. For mapped operations,
the inspector shows assignment targets and the complete embedded Python file,
scrolls to the originating call, and highlights its source line range.

Click a rendered face or CAD edge in the viewport to select the corresponding
evaluated entity. The selected face or edge is highlighted and its measured
properties are shown in the inspector. The scene package must contain the
embedded model artifact for the Features tab; older scene packages still retain
assembly-tree and geometry selection support.
