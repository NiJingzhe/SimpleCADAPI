<p align="center">
  <img src="img/repocover.png" alt="SimpleCADAPI 仓库封面">
</p>

# SimpleCADAPI

[English](README.md)

## 更新日志（2.0.4b3 开发中）

> **Beta 版本：** 用于生产前，请验证生成的定义、装配约束和制造几何。

SimpleCADAPI 2.0.4b3 新增可复现的 `@part`/`@assemble` 产品边界、增量装配求解，
以及整零件的持久化崩溃安全缓存。契约、cache mode、诊断、限制和验证范围见
[完整中文更新说明](docs/updates/2.0.4b3.zh-CN.md)。

---

<div align="center">
  <h2>SimpleCADAPI 论文成果</h2>
  <p>本仓库是以下论文工作的项目产物：</p>
  <p>
    <strong><a href="https://arxiv.org/abs/2608.00891">CADIR: A Cross-Backend Editable Intermediate Representation for Agentic CAD Generation</a></strong>
  </p>
  <p><strong>Computer-Aided Design 2026 接收</strong></p>
</div>

---

SimpleCADAPI 是一个基于 OCP 的 Python CAD SDK，提供清晰的函数式建模操作和可重放的模型图。它在 OpenCascade 几何内核之上提供精简的公共 API，可用于创建实体、应用特征、添加语义标签、查询拓扑、导出制造文件，以及将记录的模型转换为 FreeCAD 工作流。

当前开发 Beta：`simplecadapi==2.0.4b3`。

## 核心能力

- 基于 OCP 的 `Vertex`、`Edge`、`Wire`、`Face` 和 `Solid` 类型。
- 支持基本体、轮廓、拉伸、旋转、放样、扫掠、布尔运算、变换、阵列、圆角、倒角和抽壳等函数式建模操作。
- 通过显式 `GraphSession`、`export_model_json(...)`、`import_model_json(...)` 和 `replay_model_json(...)` 记录并重放操作图。
- 通过 `var(...)`、算术表达式和可序列化表达式图定义参数。
- 使用 QL 选择器定位几何、查询拓扑并稳定选择特征。
- 通过 `apply_tag(shape=..., tag=...)` 和 `list_tags(shape=...)` 管理语义标签。
- 支持 STEP/STL 导出，以及 FreeCAD 脚本和 `.FCStd` 转换。
- 面向 Agent 的 STEP/BREP 逆向能力，提供稳定实体 ID、局部诊断、区域高亮截图和
  可测量的验收门槛。
- 可回放的开放/周期插值 B 样条 Edge 和 Wire，可用于自由轮廓与 Loft 截面。
- 持久 `@part`/`@assemble` 定义、增量装配求解，以及具备损坏隔离和 JSON 诊断的
  content-addressed cache。

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

@scad.part(id="bracket")
def build_bracket() -> scad.Solid:
    base = scad.make_box_rsolid(
        width=60.0, height=36.0, depth=8.0, bottom_face_center=(0.0, 0.0, 0.0)
    )
    hole = scad.make_cylinder_rsolid(
        radius=5.0, height=14.0, bottom_face_center=(0.0, 0.0, -3.0)
    )
    body = scad.cut_rsolid(base, hole)
    return scad.apply_tag(shape=body, tag="role.demo.bracket")

result = build_bracket()
package_path = out / "bracket.scadpkg"
scad.capture(result, package_path)
print("volume", round(result.part.body.get_volume(), 3))
print("tags", scad.list_tags(shape=result.part.body))
scad.exporter.export_product_package_to_step(package_path, out / "bracket.step")
scad.exporter.export_product_package_to_stl(package_path, out / "bracket.stl")
```


## 可重放操作图

几何流程需要检查、序列化、重放或转换到其他 CAD 环境时，请使用显式
`GraphSession`：

```python
import simplecadapi as scad
from simplecadapi import GraphSession, export_model_json, replay_model_json

with GraphSession(graph_id="drilled_block") as session:
    body = scad.make_box_rsolid(
        width=40.0, height=24.0, depth=10.0,
        bottom_face_center=(0.0, 0.0, 0.0),
    )
    cutter = scad.make_cylinder_rsolid(
        radius=4.0, height=16.0, bottom_face_center=(0.0, 0.0, -3.0)
    )
    drilled = scad.cut_rsolid(body, cutter)
    session.capture_result(value=drilled)
    model_json = export_model_json(session=session)
    recorded_nodes = session.graph.node_count

rebuilt = replay_model_json(json_str=model_json)
print("recorded_nodes", recorded_nodes)
print("replayed_outputs", len(rebuilt))
```

显式 `GraphSession` 在调用导出 API 前只存在于内存。需要持久 CAD/Viewer
交付物时，一个物理单实体零件使用 `@scad.part`，装配使用 `@scad.assemble`，
直接调用 `scad.capture(result, "out/product.scadpkg")`，一次完成捕获和写盘。
`.scadpkg` 包含完整定义闭包、求值场景、特征图、源码快照、拓扑以及渲染/选择资源。
STEP、STL、FCStd 和底层 JSON 仍由显式导出 API 生成。

## 持久产品构建与缓存

一个物理单实体零件使用 `@scad.part`；具有显式外部定义的装配使用
`@scad.assemble`。同 build key 的 PRT 在进程内直接复用，持久 part bundle 则跨运行复用未变 PRT。

```python
@scad.part(id="mounting_plate", cache="auto")
def build_plate(width: float = 30.0) -> scad.Part:
    body = scad.make_box_rsolid(width=width, height=20.0, depth=3.0)
    return scad.make_part_rpart(part_id="mounting_plate", body=body)

cold = build_plate()
warm = build_plate()
print(cold.cache_report.hit, warm.cache_report.hit)
```

缓存检查和维护命令输出稳定 JSON：

```bash
simplecad-cache status
simplecad-cache verify
simplecad-cache prune
```

cache mode、配置优先级、PRT 复用、增量失效、损坏修复和破坏性命令确认见
[持久缓存与产品构建工作流](docs/guides/cache-build-workflow.md)。

## STEP/BREP Agent 逆向

需要生成同步 STEP 视图或局部高亮截图时，请安装渲染依赖：

```bash
pip install "simplecadapi[inverse-engineer]"
```

专用命名空间 `simplecadapi.inverse_engineer.brep` 提供稳定的
Body/Face/Edge/Vertex ID，以及与 Agent 框架无关的工具注册表。逆向时应先读取
有界证据，只有在候选模型足够接近后，才执行成本较高的材料差集或严格拓扑检查：

```python
from simplecadapi.inverse_engineer import brep

schemas = brep.agent_tool_schemas()
summary = brep.call_agent_tool(
    name="get_model_summary",
    arguments={
        "model_path": "target.step",
        "include_parameter_groups": True,
    },
)
face = brep.call_agent_tool(
    name="inspect_entity",
    arguments={"model_path": "target.step", "entity_id": "face:0"},
)

print("tools", len(schemas))
print("faces", summary["face_count"])
print("carrier", face["geometry"]["type"])
```

CLI 使用同一份工具契约：

```bash
simplecad-brep tools
simplecad-brep tool get_model_summary --arguments-file summary-args.json
```

受控测试请使用 [Reconstruction Agent 测试规范](docs/guides/reconstruction-agent-test-prompt.md)，
完整证据、建模、回放和验收流程请阅读
[STEP BREP 逆向工程指南](docs/guides/step-brep-reverse-engineering.md)。

## FreeCAD 转换

外部 CAD 转换只接受经过验证的 `.scadpkg` 产品包：

```python
package_path = artifacts.artifact_paths["product"]
script = scad.translator.freecad_translator.translate_product_package_to_freecad_script(
    package_path
)
scad.translator.freecad_translator.translate_product_package_to_fcstd(
    package_path, "bracket.FCStd"
)
scad.exporter.export_product_package_to_step(package_path, "bracket.step")
scad.exporter.export_product_package_to_stl(package_path, "bracket.stl")
```

## 文档

- 2.0.4b3 更新说明：[`docs/updates/2.0.4b3.zh-CN.md`](docs/updates/2.0.4b3.zh-CN.md)
- Reconstruction Agent 测试规范：
  [`docs/guides/reconstruction-agent-test-prompt.md`](docs/guides/reconstruction-agent-test-prompt.md)
- STEP BREP 逆向工程指南：
  [`docs/guides/step-brep-reverse-engineering.md`](docs/guides/step-brep-reverse-engineering.md)
- 持久缓存与产品构建工作流：
  [`docs/guides/cache-build-workflow.md`](docs/guides/cache-build-workflow.md)
- 公共 API 参考：[`docs/api/`](docs/api/)
- 核心类型与建模说明：[`docs/core/`](docs/core/)
- 序列化与重放：[`docs/core/serialization/README.md`](docs/core/serialization/README.md)
- 操作图 JSON 规范：[`docs/core/operation_graph_json_spec.md`](docs/core/operation_graph_json_spec.md)
- 示例索引：[`examples/README.md`](examples/README.md)
  `.scadpkg` 产品包规范：[`design-docs/scadpkg-spec.md`](design-docs/scadpkg-spec.md)

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
