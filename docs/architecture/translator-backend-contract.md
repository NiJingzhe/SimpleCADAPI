# Translator Backend Contract

This contract defines the package structure and dependency boundaries for every
SimpleCAD translator backend.

## Backend Naming

Backend packages live under `simplecadapi.translator` and use the name
`<backend>_translator`, where `<backend>` is a stable lowercase backend ID.

Examples:

- `freecad_translator`
- `openscad_translator`
- `onshape_translator`

Backends are exported explicitly from `simplecadapi.translator`. Importing a
backend package must not require the target CAD runtime to be installed.

## Required Files

Every backend package contains:

| File | Responsibility |
| --- | --- |
| `__init__.py` | Defines the complete public backend surface through `__all__`. |
| `api.py` | Contains public convenience functions and user-facing error boundaries. |
| `translator.py` | Contains the `<Backend>Translator` implementation. |
| `capabilities.py` | Declares backend targets and support for every canonical operation. |

The translator class must inherit `BaseTranslator`. `capabilities.py` exports
`BACKEND_NAME`, `CAPABILITIES`, and `OP_SUPPORT`. The operation support map must
contain exactly the canonical operation set. Unsupported operations require a
non-empty reason.

## Conditional Files

Use these standard names when the corresponding responsibility exists:

| File or directory | Responsibility |
| --- | --- |
| `exporter.py` | File output, external process or remote API execution, and output validation. |
| `context.py` | State owned by one translation invocation. |
| `analysis.py` | Backend-specific graph analysis and lowering decisions. |
| `codegen.py` | Pure target-code formatting and literal helpers. |
| `emitters/` | Canonical operation emitters and their single registry. |
| `runtime/` | Source fragments embedded into an artifact for execution in the target runtime. |

An `emitters/registry.py` file is the only operation-to-emitter mapping. Runtime
fragments must remain valid Python source, must not execute target APIs when the
SimpleCAD package is imported, and must be assembled in one declared order.

## Translation And Export

Translation is an in-memory operation. It consumes canonical model JSON or an
already imported canonical payload and returns a `TranslationArtifact`.

Export is an effectful operation. It may write files, invoke an executable, or
call a remote API. Those effects belong in `exporter.py`, not in the translator
or emitters.

Public naming follows these forms:

- `translate_model_json_to_<artifact>` for in-memory conversion.
- `export_model_json_to_<format>` for file or external-runtime output.

Existing public names may remain as compatibility aliases.

## Dependencies

The allowed dependency direction is:

```text
backend/__init__.py -> api.py, translator.py, capabilities.py
api.py              -> translator.py, exporter.py
translator.py       -> context.py, analysis.py, emitters/, runtime/
emitters/           -> context and pure code-generation helpers
exporter.py          -> shared types/errors and external execution
```

The following reverse dependencies are prohibited:

- Translator or emitters importing `api.py`.
- Translator importing `exporter.py`.
- Emitters importing the public translator class.
- Runtime fragments importing the backend package.
- Capabilities importing translator implementation modules.

## Compatibility

The generated artifact and its persisted target metadata are treated as a
compatibility boundary. Pure module moves must not rename generated runtime
helpers, registries, target object properties, or public import paths. Behavior
fixes are made separately from structural migrations.

## Verification

The shared backend contract test verifies required files, public exports,
translator inheritance, backend naming, and canonical operation coverage.
Backend tests additionally verify generated artifact syntax and, where the
target runtime is available, real exported files.
