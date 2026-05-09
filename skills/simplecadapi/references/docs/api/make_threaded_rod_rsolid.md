# make_threaded_rod_rsolid

## API Definition

```python
def make_threaded_rod_rsolid(thread_diameter = 8.0, thread_length = 20.0, total_length = 30.0, thread_pitch = 1.25, thread_start_position = 0.0, chamfer_size = 0.5) -> Solid
```

*Source: evolve.py*

## Description

Create a threaded rod with configurable rod length, thread span, and pitch. The top center is placed at the origin and the rod extends in -Z.
