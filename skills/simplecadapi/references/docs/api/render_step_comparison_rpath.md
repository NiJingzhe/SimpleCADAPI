# render_step_comparison_rpath

```python
render_step_comparison_rpath(target_step_path, current_step_path, output_path, *, views=DEFAULT_VIEWS, image_size=(16.0, 20.0), dpi=160, linear_deflection=0.12, angular_deflection=0.18, show_brep_edges=True) -> Path
```

Inspection namespace. Renders Original and Reconstructed STEP models side by
side using the same view directions, union bounds, camera scale, tessellation,
and BREP-edge settings. The image is diagnostic evidence and does not replace
strict geometric or topology comparison.
