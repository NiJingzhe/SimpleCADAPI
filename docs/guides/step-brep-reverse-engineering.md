# STEP BREP 逆向工程方法

该方法论是 SimpleCAD skill 的任务专用参考，规范版本位于：

```text
skills/simplecadapi/references/inverse_engineer/brep-reverse-engineering.md
```

正式检查工具位于：

```text
src/simplecadapi/inverse_engineer/brep/
```

Python API：

```python
from simplecadapi.inverse_engineer import brep

report = brep.inspect_step(path="part.step")
comparison = brep.compare_steps(target_path="target.step", candidate_path="candidate.step")
brep.render_step_views(step_path="candidate.step", output_path="candidate-views.png")
brep.compare_step_slices(
    target_path="target.step",
    candidate_path="candidate.step",
    output_path="slice-overlay.png",
)
```

渲染和图片截面功能需要可选依赖：

```bash
uv sync --extra inverse-engineer
```

CLI：

```bash
uv run simplecad-brep inspect part.step -o part-report.json
uv run simplecad-brep compare target.step candidate.step -o comparison.json
uv run simplecad-brep render candidate.step candidate-views.png
uv run simplecad-brep slices target.step candidate.step slice-overlay.png
```

具体逆向案例见：

```text
examples/out/xzby_reverse/README.md
```
