# inspect_benchmark_step

## API Definition

```python
def inspect_benchmark_step(path: str | Path, *, name: str, output_directory: str | Path, timeout_seconds: float, python_executable: str = sys.executable) -> dict[str, Any]
```

*Source: inverse_engineer/brep/evaluation.py*

## Import Surface

- reverse-engineering evaluator: `from simplecadapi.inverse_engineer.brep import inspect_benchmark_step`

## Description

Inspect one candidate or target STEP in a bounded worker process.
