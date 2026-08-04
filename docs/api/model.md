# model

## API Definition

```python
def model(func: Optional[Callable[_P, _R]] = None, *, graph_id: Optional[str] = None, export_dir: str | Path | None = None) -> Union[Callable[[Callable[_P, _R]], Callable[_P, ModelResult]], Callable[_P, ModelResult]]
```

*Source: graph.py*

## Import Surface

- top-level: `from simplecadapi import model`

## Description

Decorate a top-level model function with one owned ``GraphSession``.
