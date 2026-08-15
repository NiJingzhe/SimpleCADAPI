# inspect_benchmark_step

## API Definition

```python
def inspect_benchmark_step(path: str | Path, *, name: str, output_directory: str | Path, timeout_seconds: float, python_executable: str = sys.executable) -> dict[str, Any]
```

*Source: inverse_engineer/brep/evaluation.py*

## Import Surface

- reverse-engineering evaluator: `from simplecadapi.inverse_engineer.brep import inspect_benchmark_step`

## Description

Inspect one candidate or target STEP in a bounded trusted worker.

The returned stage envelope has ``status`` (``passed``, ``failed``, or
``error``), boolean ``gate_passed``, ``elapsed_seconds``, ``report``,
``report_path``, and ``error``. A completed report contains ``valid`` and
``counts``; classification uses the integer ``solid`` and ``shell`` counts.
Lengths are millimetres, area is square millimetres, volume is cubic
millimetres, and elapsed time is seconds.

The process is isolated from participant Python paths and a timeout kills its
entire process tree. Only the unmodified process-local result of this trusted function may
be supplied to ``classify_benchmark_result``; a participant-authored
inspection report or claimed shape kind is not acceptance evidence.
