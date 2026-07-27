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
active `GraphSession`. The decorator reuses the session owned by the enclosing
`@model` function and validates that returned graph values belong to it.

```python
@scad.requires_session
def make_bracket_body():
    return scad.make_box_rsolid(width=20.0, height=10.0, depth=3.0)
```

Calling a `@requires_session` builder without an active session raises
`RuntimeError`. Builders must not create their own `GraphSession`.
