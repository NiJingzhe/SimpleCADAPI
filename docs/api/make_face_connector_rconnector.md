# make_face_connector_rconnector

## API Definition

```python
def make_face_connector_rconnector(connector_id: str, face: Face, name: Optional[str] = None, flip: bool = False) -> Connector
```

*Source: operations.py*

## Import Surface

- top-level: `from simplecadapi import make_face_connector_rconnector`

## Description

Create a connector anchored to a Face.

Z axis follows the face normal; origin is the face center.
Set flip=True to negate the Z axis (point it opposite to the normal).
