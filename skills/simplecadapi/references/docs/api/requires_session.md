# requires_session

## API Definition

```python
def requires_session(func=None) -> Callable
```

*Source: graph.py*

## Import Surface

- top-level: `from simplecadapi import requires_session`

## Description

Decorate a reusable graph-producing builder that must run inside the caller's
active `GraphSession`. It reuses the session owned by the enclosing `@model`
function and validates returned graph values against that session.

Calling a `@requires_session` builder without an active session raises
`RuntimeError`. Builders must not create their own `GraphSession`.
