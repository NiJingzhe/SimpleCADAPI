# run_comparison_bundle

## API Definition

```python
def run_comparison_bundle(config: EvaluationConfig, *, target_path: str | Path, candidate_path: str | Path, output_directory: str | Path, diagnostics: bool = False, strict_topology: bool = False, python_executable: str = sys.executable) -> dict[str, dict[str, Any]]
```

*Source: inverse_engineer/brep/evaluation.py*

## Import Surface

- reverse-engineering evaluator: `from simplecadapi.inverse_engineer.brep import run_comparison_bundle`

## Description

Run acceptance proof, with geometric diagnostics only when requested.
