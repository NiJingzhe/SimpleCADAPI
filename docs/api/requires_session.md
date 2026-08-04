# requires_session

## API Definition

```python
def requires_session(func: Optional[Callable[_P, _R]] = None) -> Union[Callable[[Callable[_P, _R]], Callable[_P, _R]], Callable[_P, _R]]
```

*Source: graph.py*

## Import Surface

- top-level: `from simplecadapi import requires_session`

## Description

Decorate a builder that must reuse the caller's active GraphSession.
