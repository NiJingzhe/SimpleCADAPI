# Engineering Guides

- [STEP BREP Reverse Engineering](step-brep-reverse-engineering.md): full workflow from STEP inspection, geometric fingerprint analysis, feature-tree inference, and candidate iteration to geometric point-set, BREP topology, parameter history, and model replay acceptance.
- [Reconstruction Agent Test Prompt](reconstruction-agent-test-prompt.md):
  reusable prompt for controlled, comparable STEP reconstruction trials.
- [Persistent Cache and Product Build Workflow](cache-build-workflow.md):
  durable `@part`/`@assemble` boundaries, PRT reuse, unified cache policy,
  diagnostics, `.scadpkg` delivery, FreeCAD/AP242 targets, and optional Gmsh
  volume meshing.

The corresponding runnable module and examples live in:

```text
src/simplecadapi/inspect/brep/
```
