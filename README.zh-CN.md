<p align="center">
  <img src="img/repocover.png" alt="SimpleCADAPI 仓库封面">
</p>

# SimpleCADAPI

[English](README.md)

---

<div align="center">
  <h2>CADDesigner 论文成果</h2>
  <p>本仓库是以下论文工作的项目产物：</p>
  <p>
    <strong><a href="https://562590763.github.io/CADDesigner/">CADDesigner: Conceptual CAD Model Generation with a General-Purpose Agent</a></strong>
  </p>
  <p><strong>Computer-Aided Design 2026 接收</strong></p>
</div>

---

SimpleCADAPI 是一个基于 OCP 的 Python CAD SDK，提供清晰的函数式建模操作和可重放的模型图。它在 OpenCascade 几何内核之上提供精简的公共 API，可用于创建实体、应用特征、添加语义标签、查询拓扑、导出制造文件，以及将记录的模型转换为 FreeCAD 工作流。

当前测试版本：`simplecadapi==2.0.1b1`。

## 核心能力

- 基于 OCP 的 `Vertex`、`Edge`、`Wire`、`Face` 和 `Solid` 类型。
- 支持基本体、轮廓、拉伸、旋转、放样、扫掠、布尔运算、变换、阵列、圆角、倒角和抽壳等函数式建模操作。
- 通过 `@model`、`ModelResult`、`capture_result(...)`、`import_model_json(...)` 和 `replay_model_json(...)` 记录并重放建模过程。
- 通过 `var(...)`、算术表达式和可序列化表达式图定义参数。
- 使用 QL 选择器定位几何、查询拓扑并稳定选择特征。
- 通过 `apply_tag(shape=..., tag=...)` 和 `list_tags(shape=...)` 管理语义标签。
- 支持 STEP/STL 导出，以及 FreeCAD 脚本和 `.FCStd` 转换。

## 安装

使用 pip：

```bash
pip install simplecadapi
```

使用 uv：

```bash
uv add simplecadapi
```

从本仓库进行本地开发：

```bash
uv sync --group dev
```

## 快速开始

```python
from pathlib import Path

import simplecadapi as scad

out = Path("out")
out.mkdir(exist_ok=True)

base = scad.make_box_rsolid(
    width=60.0, height=36.0, depth=8.0, bottom_face_center=(0.0, 0.0, 0.0)
)
hole = scad.make_cylinder_rsolid(
    radius=5.0, height=14.0, bottom_face_center=(0.0, 0.0, -3.0)
)
part = scad.cut_rsolid(base, hole)
part = scad.apply_tag(shape=part, tag="role.demo.bracket")

print("volume", round(part.get_volume(), 3))
print("tags", scad.list_tags(shape=part))

scad.export_step(shapes=part, filename=str(out / "bracket.step"))
scad.export_stl(shapes=part, filename=str(out / "bracket.stl"))
```

## 可重放建模

当模型需要检查、序列化、重放或转换到其他 CAD 环境时，请使用唯一的
`@scad.model` 顶层入口。该入口拥有自己的 `GraphSession` 并返回 `ModelResult`：

```python
import simplecadapi as scad

@scad.model(graph_id="drilled_block")
def build_model():
    body = scad.make_box_rsolid(
        width=40.0, height=24.0, depth=10.0,
        bottom_face_center=(0.0, 0.0, 0.0),
    )
    cutter = scad.make_cylinder_rsolid(
        radius=4.0, height=16.0, bottom_face_center=(0.0, 0.0, -3.0)
    )
    drilled = scad.cut_rsolid(body, cutter)
    scad.capture_result(value=drilled)
    return drilled

result = build_model()
model_json = result.model_json
rebuilt = result.replay()

print("recorded_nodes", result.session.graph.node_count)
print("replayed_outputs", len(rebuilt))
```

如果模型调用还需要写出最终文件，请向 `@scad.model` 传入
`export_dir=...`。显式 `capture_result(...)` 的结果会生成一个自包含的
`<graph_id>.scene.zip`，其中包含 `scene.json`、`model/model.json`、operation
source mapping 引用的完整项目相对 Python 源文件（位于 `sources/`）以及
Viewer 所需的 GLB/entity 资源。自动导出不会在旁边生成 model/session JSON、
STEP、STL 或 FCStd；这些格式仍可通过显式导出 API 生成。文件路径为
`result.artifact_paths["scene"]`。省略 `export_dir` 时不会写文件。

## FreeCAD 转换

可以把记录的模型 JSON 转换为 FreeCAD Python 脚本：

```python
script = scad.translator.freecad_translator.translate_model_json_to_freecad_script(model_json)
```

如果系统中存在 FreeCAD 或 FreeCADCmd，也可以直接生成 `.FCStd` 文件：

```python
scad.translator.freecad_translator.translate_model_json_to_fcstd(model_json, "bracket.FCStd")
```

## 文档

- 公共 API 参考：[`docs/api/`](docs/api/)
- 核心类型与建模说明：[`docs/core/`](docs/core/)
- 序列化与重放：[`docs/core/serialization/README.md`](docs/core/serialization/README.md)
- 操作图 JSON 规范：[`docs/core/operation_graph_json_spec.md`](docs/core/operation_graph_json_spec.md)
- 示例索引：[`examples/README.md`](examples/README.md)

## 发布 Agent Skill

仓库中的 `skills/simplecadapi/` 是精简版 Agent Skill。它包含生成的 API 和建模参考文档，但不包含 SDK 源代码。

在干净的工作区中更新项目版本和文档，然后生成并验证发布产物：

```bash
uv sync --group dev
uv run skill-pack --refresh-docs --archive
uv run python -m pytest test/test_skill_pack.py
```

该命令会刷新生成文档、重建 `skills/simplecadapi/`，并生成 `skills/simplecadapi.tar.gz`。发布前检查 Skill 内容和归档文件：

```bash
git diff -- skills/simplecadapi docs
tar -tzf skills/simplecadapi.tar.gz
```

发布时提交生成的 `skills/simplecadapi/` 目录和更新后的 `docs/`。归档文件已被 Git 忽略；请将 `skills/simplecadapi.tar.gz` 附加到对应的 GitHub Release，或上传到目标 Agent Skills 注册中心。

## 开发

```bash
uv sync --group dev
uv run python -m pytest test tests
python3 -m compileall src/simplecadapi
```

## 许可证

本项目采用 GNU Affero 通用公共许可证第 3 版（AGPL-3.0），详见 [`LICENSE`](LICENSE)。

## 社区交流

由于群聊人数过多，无法直接扫码入群。请扫描下方二维码添加杜鹏老师微信，由杜鹏老师邀请加入 CADDesigner 技术交流群：

<p align="center">
  <img src="img/dp个人账号.png.jpg" alt="杜鹏老师个人微信二维码" width="420">
</p>
