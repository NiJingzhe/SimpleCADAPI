# render_plan

## API Definition

```python
def render_plan(plan, dxf_path, png_path)
```

*Source: dxf_engine/render.py*

## Import Surface

- drawing namespace: `from simplecadapi.dxf_engine import render_plan`

## Description

把求解后的 SheetPlan 渲染为 GB 图层 DXF + PNG 双产物。

DXF 走 ezdxf（手工基元：细实线尺寸线/界线、实心箭头、旋转归一文字、
GB 图层 01粗实线/08虚线/05中心线/尺寸标注/文字），PNG 经 PyMuPdf 由
DXF 转出用于多模态互校验。同时写出便于版本 diff 的文本化动作日志。
