# SimpleCAD Evaluated Scene 与 Viewer 架构设计

## 文档状态

- 状态：Frozen（Scene Schema 1.0 Phase A contract）
- 冻结证据日期：2026-07-22
- Shared corpus：`test/fixtures/scene-contract/corpus.json`，SHA-256 `4f04224333e6aa70b12fc33efaee7b8d27782894d692fe402a6ef1d394a780ca`
- 目标版本：Scene Schema 1.0
- 目标项目：SimpleCADAPI 2.x
- 依赖：现有 Model Schema 2.0、Product/Assembly 语义、内部三角化能力、glTF 2.0、RFC 8785 JSON Canonicalization Scheme (JCS)
- 主要影响模块：`src/simplecadapi/scene/` 中的 compiler、render mesh/asset、serializer、validator 和 contract artifacts，`source_mapping.py`，以及仓库根目录下独立的 `viewer/` TypeScript/Three.js 工程；现有 `graph.py`、`serializer.py`、`product.py`、`_mesh.py` 提供输入
- 非目标：用 scene 文件替代 operation graph、在浏览器中重放全部 CAD operations、第一阶段提供协同编辑或通用游戏引擎、把 viewer 临时状态写回 canonical model

### 当前实现边界

当前仓库已经具有 replayable operation graph、`ModelResult`、显式 result capture、`Part`/`Assembly`/`Component` 产品层级、刚体 placement、基础 material RGB、Phase A 冻结的 Scene Schema、immutable contract documents、strict validators、resource profiles、exact GLB/ZIP vectors、Python/TypeScript parity harness，以及可工作的 Scene Compiler、triangle/edge GLB writer、entity sidecar、canonical `.scene.zip` exporter和browser Viewer。Viewer当前是直接DOM状态管理的TypeScript/Three.js/Vite应用，支持package loading、product tree、Features/source inspection和五种selection intent；尚未实现presentation/imported compilation、scene patch protocol、持久化workspace、独立model/scene pair-state系统或browser CAD replay。

本文将现有 `model.json` 定义为 parametric design/replay IR，将新增的 scene 文件定义为 evaluated presentation artifact。Scene 可以由 model 和可选 `ScenePresentationSpec` 重建，但不能反向替代二者，也不能成为表达设计或 presentation authoring intent 的第二份事实来源。

## 1. 摘要

SimpleCADAPI 接下来需要一层独立于 Operation Graph 的 evaluated scene，用于回答以下问题：

1. 当前应该显示哪些对象。
2. 对象之间是什么产品或实例层级。
3. 每个实例的局部变换是什么。
4. 每个实例引用哪个可渲染 geometry asset 和 appearance。
5. 用户点击一个 triangle、face 或 component 时，如何追溯到 scene node、product component、graph output 和 semantic evidence。
6. Viewer 在不运行 OpenCascade replay 的情况下，如何直接加载并显示模型。
7. 同一 part 被多次实例化时，如何只保存一份 mesh。
8. 几何变化、placement 变化和纯显示变化如何采用不同的缓存与更新策略。

推荐的数据流为：

```text
Python modeling source
        |
        v
Operation Graph / model.json
        |
        | replay or direct runtime evaluation
        v
Solid / Part / Assembly values
        |
        | Scene Compiler
        v
SceneSnapshot / scene.json
        |
        +---- content-addressed GLB assets
        +---- evaluated entity snapshots and picking maps
        +---- generic package: optional embedded model.json
        +---- self-contained model package:
        |       model/model.json
        |       sources/<project-relative-path>.py
        |
        v
Browser Viewer / Desktop Viewer
```

核心决策是：

> `model.json` 描述模型如何构建，`scene.json` 描述模型求值后如何被显示和交互，render assets 描述 GPU 实际绘制的数据，workspace 描述某个用户当前的临时界面状态。

## 2. 为什么不能直接让 Viewer 消费 Operation Graph

Operation Graph 的边表达 operation data dependency，而不是 scene parent/child hierarchy。一个 operation node 可以是 profile、selection、boolean、constraint、material assignment 或 diagnostic semantic operation；它不一定对应一个可见对象。

如果 Viewer 直接消费 operation graph，就必须承担以下职责：

- 理解并实现全部 canonical CAD operations。
- 在浏览器中运行 OpenCascade 或等价 CAD kernel。
- 解析 operation output、semantic output 和 product output 的不同类型。
- 根据 graph leaves 推测 visibility。
- 根据 product operations 重建 definition/instance hierarchy。
- 自行生成三角网格、法线、边线和 picking 映射。
- 跟随每次 schema 或 operation set 变化升级执行器。

这会把 Viewer 变成第二个 CAD replay backend，显著增加前后端一致性成本，也使一个只想查看模型的客户端必须信任并执行完整建模程序。

Scene Snapshot 应当是已经求值的、可验证的、有限能力的显示数据。Viewer 只需要理解 scene/render asset schema；为只读Features和源码inspection，它可以解析embedded model graph的有限记录，但不会实现或执行fillet、loft、constraint solve或CADQL。读取operation records用于展示不等于把Viewer变成CAD replay backend。

## 3. 六种 Artifact 的边界

### 3.1 Design Model

当前 `model.json` 属于 Design Model，canonical owner 包括：

- Operation DAG 和 operation params。
- Expression intent 和 numeric snapshot。
- Tolerance requirements。
- Feature selection intent。
- Semantic bindings。
- Topology evolution evidence。
- Product construction operations。
- Replay result node IDs。

Design Model 的主要用途是 replay、编辑、参数修改、translator 和设计审计。

### 3.2 Evaluated Scene

新增 `scene.json` 属于 Evaluated Scene，canonical owner 只包括某次编译的 evaluated snapshot：

- 某个 scene revision 的 node hierarchy。
- Definition/instance 引用关系。
- Parent-relative rigid transforms。
- Geometry asset 和 appearance 绑定。
- 编译后的 Scene visibility、selectability 和 display organization。
- Scene-level source provenance。
- 由 `ScenePresentationSpec` 求值后的 named views 和 appearance overrides；annotations 在后续 extension 中引入。
- Definition-local evaluated topology/entity snapshot 引用。

Scene 是 source model 与 optional presentation spec 某次求值的快照。任一 source 更新后 Scene 都可以失效并重新编译。Generated scene 本身不是 authoring source。

### 3.3 Render Assets

Render Assets 负责保存：

- Vertex positions。
- Vertex或corner normals。
- Triangle indices。
- CAD edge polylines。
- Local bounds。
- Face/edge picking ranges。
- Tessellation settings。

第一阶段推荐两个 appearance-neutral GLB profile：triangle geometry asset 和 CAD edge line asset。独立 `EntitySnapshotAsset` 保存 definition/source-specific evaluated topology、geometry properties、SDK tags/metadata、operation provenance 和 picking map。Asset 使用内容哈希寻址，支持不同 scene revision 复用；同一 geometry bytes 可以对应多个 provenance/metadata 不同的 entity snapshot assets。

### 3.4 Viewer Workspace

Viewer Workspace 负责某个用户或某次查看会话的临时状态：

- 当前 camera pose。
- Hover 和 selection。
- 用户临时隐藏的节点。
- Tree 展开状态。
- Clipping planes。
- Exploded view amount。
- 当前 display mode。
- Panel layout 和 measurement history。

Workspace 默认不属于 canonical scene，也不能修改 model semantics。若需要分享视图，用户必须把明确选择的 workspace state 发布为独立 `ScenePresentationSpec`，然后重新编译 scene。

### 3.5 Scene Presentation Spec

`ScenePresentationSpec` 是可选 authoring artifact，负责不可从 model 确定性重建的发布意图：

- Named cameras/views。
- Authored visibility 和 appearance overrides。
- Labels、callouts 和 read-only dimensions。
- Authored section presets。

它拥有独立 schema、logical ID 和 artifact hash，并作为 `compile_scene(..., presentation=...)` 的显式输入。没有 presentation spec 时，compiler 只生成 deterministic defaults，不从之前生成的 scene 反向读取 authoring state。

### 3.6 Connector Binding Spec

`ConnectorBindingSpec` 是 Viewer/Editor 产生的 revision-bound authoring command，不是 evaluated scene 的一部分。它保存用户选择的 owner、target entity、connector ID、方向选项和 source model/scene preconditions。Python SDK 或受控 backend 验证这些 preconditions，通过trusted deterministic recompilation把revision-local entity解析回唯一live geometry selection、调用canonical connector operation，并生成新的`model.json`和`.scene.zip`。

Connector binding 的 canonical owner 最终仍是 Design Model 中的 connector operations/Product semantics。Binding spec 可以作为审计或重试 command 保存，但不能只修改 scene snapshot 后宣称 model 已被编辑。

## 4. Canonical Owner 原则

每项事实只能有一个 canonical owner。Scene 可以保存从 model 求值得到的缓存，但必须标记来源和失效条件。

| 事实 | Canonical owner | Scene 中的表示 |
| --- | --- | --- |
| Box、fillet、boolean 如何构建 | Operation Graph | 不复制 operation semantics |
| 参数表达式和尺寸链 | Expression/Tolerance Graph | 可复制只读摘要，不可编辑为第二份参数源 |
| Assembly definition 和 constraints | Product semantics in model | Scene 保存求值后的 hierarchy、transform 和可选 kinematic projection |
| 当前 component placement | Evaluated product state | Scene node local transform |
| Part 的实体几何 | Replayed BRep value | Content-addressed render asset |
| Material 的物理密度 | Product `Material` | Scene appearance 可引用 source material ID，但不拥有密度 |
| Base color、roughness 等显示属性 | Product-to-appearance deterministic rule 或 `ScenePresentationSpec` | Scene 保存 evaluated Appearance |
| Face 的 semantic tag | Semantic Binding Store | Entity snapshot 中保存 evaluated tag cache 和 binding IDs |
| SDK shape metadata | Runtime/replayed shape metadata | Entity snapshot 保存 JSON-safe snapshot |
| Engine geometry facts | Evaluated OCP BRep | Entity snapshot 保存 typed geometry property snapshot |
| Triangle 属于哪个 face | Definition-specific Entity Snapshot Asset | Scene definition 引用 picking range |
| 当前 hover/selection | Viewer Workspace | 不进入 scene snapshot |
| 作者保存的默认视角 | `ScenePresentationSpec` | Scene 保存 evaluated named camera/view |
| 用户临时相机 | Viewer Workspace | 不进入 canonical scene |
| Connector 定义和 geometry anchor intent | Design Model/Product semantics | Scene 保存 evaluated connector snapshot |
| Viewer 发起的 connector 绑定命令 | `ConnectorBindingSpec`，成功后归并到 Design Model | 不直接修改已有 scene revision |

## 5. 与 `capture_result` 的关系

`capture_result` 继续只定义 Design Model 的 replay outputs。它回答：

> 哪些 graph-backed values 是 canonical model results。

它不回答：

- 哪些 intermediate objects 在 Viewer 中可见。
- 哪个 assembly 应该作为 scene root。
- Camera、lights 或 background 是什么。
- Component tree 如何展开。
- Geometry 使用哪个 tessellation quality。
- Viewer 当前选中了什么。

第一阶段不扩展 `capture_result` 的职责，也不增加隐式 display metadata。Low-level Scene compilation 使用显式 root descriptor：

```python
result = build_gearbox()
assembly, preview = result.value

package = scad.compile_scene(
    scene_id="gearbox-demo",
    roots=(
        scad.SceneRoot(root_id="main", value=assembly),
    ),
    source=result,
    options=scad.SceneCompileOptions(embed_source=True),
)
scad.export_scene(package=package, path="gearbox.scene.zip")
```

Base 1.0 `roots`只接受一个或多个显式`SceneRoot(root_id=..., value=..., transform=..., source_element_id=...)`，不接受裸runtime values，因为裸value没有stable root namespace。Model/manual source中`source_element_id`必须省略，`value`允许`Solid`、含至少一个valid solid的`Compound`、`Part`或`Assembly`。Imported source中`source_element_id` required，必须是importer/caller从exact source artifact提供的stable non-empty element identity，`value`只允许`Solid`或上述`Compound`；Base 1.0不为imported `Part`/`Assembly`发明product provenance。`source_element_id`不能从root sequence、runtime traversal或temporary file path生成，UTF-8长度必须不超过structural ID budget。`transform`省略时规范化为第7.4节exact identity transform；显式transform必须valid rigid transform。Tuple输入在compile开始时按`root_id` unsigned UTF-8 byte order规范化，因此caller sequence不影响manifest；duplicate root ID在sort前失败。

如果只有 `model.json`，调用端先 replay captured results，再显式包装为 `SceneRoot`。若 captured result 只包含 flattened compound，scene compiler 只能生成 flat geometry scene，不能凭空恢复已经丢失的 product hierarchy。`root_id` 在一个 scene 内唯一，为 multi-root definition 和 occurrence identity 提供 namespace；compiler 不依赖 sequence position 生成 ID。

因此，产品模型若需要保留 hierarchy，至少应满足以下一项：

1. `capture_result(value=assembly)` 将 assembly 作为 model result。
2. Runtime CLI 直接把 `ModelResult.value` 中的 assembly 传给 `compile_scene`。
3. 后续 schema 显式增加 product result role，但不通过猜测 downstream compound 反推 assembly。

当前还提供显式opt-in的publishing shortcut：`@model(graph_id=..., export_dir=...)`在model调用结束后自动执行`ModelResult.export_artifacts()`；也可以先取得`ModelResult`，再手动调用`result.export_artifacts(output_dir=...)`。如果作者没有调用`capture_result()`，`@model`先把返回值作为result capture。自动路径从captured values导出`Part`/`Assembly`，没有product value时才导出`Solid`/`Compound`，为roots分配`capture-<index>`，使用`scene_id=graph_id`，强制嵌入model和可解析Python source，并且在output directory外部只写一个`<graph_id>.scene.zip`。它不旁置写出model/session JSON、STEP、STL或FCStd。

## 6. 当前能力与缺口

### 6.1 已有能力

| 能力 | 当前来源 | Scene Compiler 可直接复用 |
| --- | --- | --- |
| Graph provenance | `OperationNode`、`TopoRef`、graph attachment | 是 |
| Explicit model results | `GraphSession.result_node_ids` | 是，但只作为 fallback root evidence |
| Product hierarchy | `Assembly.components` | 是 |
| Repeated part instance | `Component.item` definition reference | 是 |
| Rigid placement | `Placement` | 是 |
| Basic material color | `Material.color` | 是 |
| Triangle/edge render mesh | `RenderMesh`、`RenderEdgeMesh` | 已接入Scene Compiler |
| Face/edge picking range | Entity sidecar groups | 已接入Viewer selection |
| Local bounds | `TriMesh.bounds` | 是 |
| Static collision traversal | Recursive component path + placement composition | 是，可复用 traversal semantics |
| Static screenshot | Existing tessellation and shading code | 只复用经验，不复用 Matplotlib renderer contract |
| Canonical Scene package | `CompiledScenePackage`、`.scene.zip` exporter | 已实现 |
| Source mapping | `OperationNode.source`、`source_files` | 已接入Features/source pane |
| Browser frontend | TypeScript/Three.js/Vite Viewer | 已支持package、tree、Features和五种selection |

### 6.2 仍缺少的核心能力

| 缺口 | 对 Viewer 的影响 |
| --- | --- |
| Presentation compilation 尚未实现 | 不能从authored spec生成named views/overrides |
| Imported source compilation 尚未实现 | 第一阶段compiler只接受manual/model runtime values |
| Browser尚无独立model/scene pairing | 当前只从一个validated package发现embedded model |
| Browser尚无完整operation/entity双向cross-link | Features和geometry inspector当前是独立selection flows |
| Viewer缺少自动化E2E harness | Source滚动/高亮主要依靠build和人工验证 |
| 没有 patch protocol | 每次变化只能全量刷新 |
| 没有 exact measurement boundary | Mesh Viewer 只能近似测量任意 geometry |

## 7. Scene Schema 1.0 总体结构

Scene JSON 顶层推荐结构如下：

```json
{
  "schema_version": "1.0",
  "extensions_used": [],
  "extensions_required": [],
  "extensions": {},
  "scene_id": "gearbox-demo",
  "revision": "sha256:...",
  "generator": {
    "name": "simplecadapi",
    "simplecadapi_version": "2.0.1b1",
    "ocp_version": "7.8.1",
    "ocp_bindings_version": "7.8.1",
    "python_abi": "cp312",
    "platform_tag": "macosx_14_0_arm64",
    "toolchain_hash": "sha256:...",
    "profile": "scene-1.0-ocp-glb-2"
  },
  "source": {
    "kind": "model",
    "graph_id": "gearbox",
    "model_schema_version": "2.0",
    "artifact_hash": "sha256:...",
    "embedded_artifact_uri": "model/model.json",
    "embedded_artifact_byte_length": 45678,
    "source_files": [
      {
        "path": "models/gearbox.py",
        "uri": "sources/models/gearbox.py",
        "media_type": "text/x-python; charset=utf-8",
        "byte_length": 12345,
        "content_hash": "sha256:..."
      }
    ]
  },
  "presentation_source": {
    "presentation_id": "gearbox-published-view",
    "schema_version": "1.0",
    "artifact_hash": "sha256:...",
    "embedded_artifact_uri": "presentation/presentation.json",
    "embedded_artifact_byte_length": 1234
  },
  "coordinate_system": {
    "length_unit": "mm",
    "handedness": "right",
    "up_axis": "+Z"
  },
  "compile_options": {
    "linear_tolerance": 0.35,
    "angular_tolerance": 0.22,
    "embed_source": true,
    "embed_presentation": true
  },
  "definitions": [],
  "nodes": [],
  "geometry_assets": [],
  "edge_assets": [],
  "appearances": [],
  "entity_assets": [],
  "connectors": [],
  "cameras": [],
  "lights": [],
  "annotations": [],
  "diagnostics": []
}
```

### 7.1 必填字段

第一阶段必填：

- `schema_version`
- `extensions_used`
- `extensions_required`
- `extensions`
- `scene_id`
- `revision`
- `generator`
- `source`
- `coordinate_system`
- `compile_options`
- `definitions`
- `nodes`
- `geometry_assets`
- `edge_assets`
- `appearances`
- `entity_assets`
- `connectors`
- `cameras`
- `lights`
- `annotations`
- `diagnostics`

这些 collection 在没有内容时仍以空 array/object 输出，不通过 missing/empty 两种状态表达额外语义。`presentation_source` 是 optional，且只有存在 presentation spec 时允许出现。

Base 1.0固定`extensions_used=[]`、`extensions_required=[]`、`extensions={}`和`diagnostics=[]`。Compiler validation/compilation failure通过`SceneValidationReport`返回，不生成带warning/error diagnostic的canonical scene。以后如需发布diagnostics或extensions，必须使用新base schema或完整注册的profile；Base 1.0 loader拒绝任一non-empty value。Workspace runtime error也不写回scene。

`SceneValidationReport`的非manifest diagnostic record结构固定为：

```json
{
  "severity": "warning",
  "code": "topology_provenance_unavailable",
  "path": "/definitions/0",
  "message": "Entity ranges are available without model topology provenance."
}
```

`severity`只允许`info`、`warning`、`error`；`code`使用normative semantic rule ID，`path`使用RFC 6901 JSON Pointer。Message是human-readable且不参与artifact identity。Runtime loader/network/GPU diagnostics属于workspace，不修改scene revision。

`source` 对所有 scene 必填，并且是 discriminated union：

- `kind=model`：必须包含 graph/model schema 和 exact input artifact bytes 的 SHA-256 `artifact_hash`；self-contained model package还包含embedded model和`source_files`。
- `kind=imported`：必须包含 imported artifact format 和 exact bytes hash。
- `kind=manual`：必须包含调用方提供的 stable `source_id`。

这里的 `artifact_hash` 不是尚未定义的 canonical model digest。对于当前 `ModelResult`，它只是 `result.model_json.encode("utf-8")` 的 exact-byte SHA-256。若 package 内嵌 source artifact，URI、byte length 和 hash 必须在加载、下载或 replay 前一致；只改变 model JSON formatting 也会改变 source artifact hash 和 scene revision，这是 Scene 1.0 可接受的保守失效策略。每个Python file独立声明其exact bytes的`content_hash`和`byte_length`，这些records作为manifest内容参与scene revision，但不改变`artifact_hash`的含义。

`presentation_source` 只在使用 `ScenePresentationSpec` 时存在。Artifact bytes 被定义为 normalized presentation record 的 JCS bytes，`artifact_hash` 是这些 bytes 的 SHA-256，因此 `compile_scene()` 接受 parsed spec 时也能确定性重建 hash input。Presentation spec 可以嵌入 package，也可以只保留 hash；嵌入时 `embedded_artifact_uri`、`embedded_artifact_byte_length` 必填，且文件内容必须恰好是上述 JCS bytes。生成的 cameras、visibility 和 appearance overrides 都必须能够追溯到这个 source。

Scene 1.0 loader只接受exact`schema_version="1.0"`；未来base schema变化必须经过显式migrator。Scene 1.0对未知base fields默认fail closed。Base validator要求三个extension containers为空；不假定所有`1.x`自动兼容，也不接受尚未注册schema/profile的optional payload。

### 7.2 Base Record 字段策略

Scene 1.0 的所有 base records 和本文定义的 entity sidecar records 都采用同一规则：表格或 discriminated union 未列出的字段一律拒绝；required 字段必须存在；optional 字段没有值时必须省略，禁止用 `null` 代替。只有下表明确标记 nullable 的字段允许 `null`。所有 map key 必须是 Unicode string，所有 number 必须是 JCS 可表示的 finite IEEE-754 binary64 value。

| Record | Required fields | Optional fields | Nullable fields |
| --- | --- | --- | --- |
| `generator` | `name`, `simplecadapi_version`, `ocp_version`, `ocp_bindings_version`, `python_abi`, `platform_tag`, `toolchain_hash`, `profile` | 无 | 无 |
| `coordinate_system` | `length_unit`, `handedness`, `up_axis` | 无 | 无 |
| `compile_options` | `linear_tolerance`, `angular_tolerance`, `embed_source`, `embed_presentation` | 无 | 无 |
| `source(kind=model)` | `kind`, `graph_id`, `model_schema_version`, `artifact_hash` | `embedded_artifact_uri`, `embedded_artifact_byte_length`, `source_files` | 无 |
| `SourceFile` | `path`, `uri`, `media_type`, `byte_length`, `content_hash` | 无 | 无 |
| `source(kind=imported)` | `kind`, `format`, `artifact_hash` | `embedded_artifact_uri`, `embedded_artifact_byte_length` | 无 |
| `source(kind=manual)` | `kind`, `source_id` | 无 | 无 |
| `presentation_source` | `presentation_id`, `schema_version`, `artifact_hash` | `embedded_artifact_uri`, `embedded_artifact_byte_length` | 无 |
| `SceneDefinition` | `definition_id`, `kind`, `name`, `source`, `sdk_metadata` | `geometry_asset_id`, `edge_asset_id`, `entity_asset_id`, `appearance_id` | `name` |
| `SceneNode` | `node_id`, `parent_node_id`, `order`, `definition_id`, `name`, `transform`, `visible`, `selectable`, `appearance_override_id`, `source`, `sdk_metadata` | 无 | `parent_node_id`, `name`, `appearance_override_id` |
| `SceneGeometryAsset` | `asset_id`, `uri`, `media_type`, `byte_length`, `content_hash`, `scene_local_bounds`, `asset_to_scene`, `tessellation` | 无 | 无 |
| `SceneEdgeAsset` | `asset_id`, `uri`, `media_type`, `byte_length`, `content_hash`, `scene_local_bounds`, `asset_to_scene`, `tessellation` | 无 | 无 |
| `SceneEntityAsset` | `entity_asset_id`, `uri`, `media_type`, `byte_length`, `content_hash` | 无 | 无 |
| `SceneAppearance` | `appearance_id`, `name`, `source`, `base_color`, `metallic`, `roughness`, `alpha_mode`, `double_sided`, `edge_color`, `sdk_metadata` | 无 | `name`, `source` |
| `SceneConnector` | `connector_snapshot_id`, `owner_definition_id`, `connector_id`, `name`, `anchor_kind`, `local_transform`, `source`, `sdk_metadata` | `target`, `forwarded_from` | `name`, `source` |
| `SceneCamera` | `camera_id`, `name`, `projection`, `parent_node_id`, `transform`, `near`, `far` and projection-specific field | 无 | `parent_node_id` |

`embedded_artifact_uri` 和 `embedded_artifact_byte_length` 必须成对出现。`SourceFile`是closed record。Schema-level generic model scene可以省略`source_files`；compiler-produced self-contained model package在嵌入model时总是输出该array，即使没有可解析的project-relative operation source而为空。`SceneDefinition.source` 是 `model_output`、`product_model`、`product_manual`、`imported`、`manual` union；`SceneNode.source` 是 `product_occurrence`、`shape_root` union。各 variant 的 exact fields 在第 8 节定义。`sdk_metadata` 必须通过第 10 节的 JSON-safe policy 规范化，不能包含 runtime object。

`generator.name`固定为`simplecadapi`。三个version fields、`python_abi`和`platform_tag`使用ASCII token grammar`[A-Za-z0-9][A-Za-z0-9._+-]{0,127}`，不得使用`2.x`、path或缺失fallback。`toolchain_hash`按第10.4节toolchain descriptor求SHA-256；它覆盖所有output-affectingPython modules、native OCP/kernel binaries和build identity。Backend只有在拥有同hash的registered toolchain时才能声称可重现scene。`generator.profile`是deterministic compiler profile ID，并参与revision。`media_type`固定为对应profile定义的exact value；Base 1.0不接受等价alias。`byte_length`是非负integer。所有content-hash IDs使用第16节的exact grammar。

Nested common records也采用exact fields：rigid transform只允许`origin`、`x_axis`、`y_axis`、`z_axis`；bounds只允许`min`、`max`；`compile_options`和geometry`tessellation`只允许positive`linear_tolerance`、positive`angular_tolerance`；edge`tessellation`只允许positive`linear_tolerance`。每个geometry asset的两个tessellation values和每个edge asset的linear value必须exact等于top-level resolved`compile_options`。`asset_to_scene`必须恰好是第7.3节固定的16-number matrix，不接受exporter-specific alternative。

Embedding conditions是exact contract：`source.kind=model|imported`且`embed_source=true`时source URI/length必须存在且bytes/hash匹配；`embed_source=false`时两者必须省略。Embedded model的URI固定为`model/model.json`。其`source_files`按`path`的unsigned UTF-8 bytes排序且唯一，每个URI必须exact等于`sources/<path>`；path必须匹配archive-safe ASCII `.py` grammar `^[A-Za-z0-9][A-Za-z0-9._/-]*\.py$`，不得有empty、`.`或`..` segment，也不得产生case-insensitive collision。每个source member必须是strict UTF-8并通过自己的length/hash验证。`presentation_source`存在且`embed_presentation=true`时其URI/length必须存在；false时省略。没有presentation时`embed_presentation`必须为false。Manual source不能embedded，要求`embed_source=false`。这两个booleans参与revision并使相同input tuple的package policy确定；其他canonical URI固定为`source/source.bin`和`presentation/presentation.json`。

Embedded model中每个operation node的source mapping是source mapping schema 1.0 closed record，exact fields为`schema_version`、`path`、`path_kind`、`line`、`column`、`end_line`、`end_column`、`call_text`、`callsite_id`和`assignment_targets`。`path_kind=project_relative`时`path`必须解析到一个manifest-declared source file，声明的source span必须与immutable file bytes中的`call_text` exact相等；`path_kind=unresolved`时`path=null`。`callsite_id`必须能从path、四个coordinates和`call_text`的canonical material重新计算。Source mapping只用于只读provenance和Viewer定位，不参与operation replay。

以下 nested records 同样是 exact contract：

- `SelectionRef(kind=component)` required且只允许 `kind`、`scene_node_id`；`SelectionRef(kind=entity)` required且只允许 `kind`、`scene_node_id`、`entity_asset_id`、`entity_id`。
- Face/edge group fields和 integer constraints由第 10.2 节定义。
- `ConnectorBindingSpec.target(kind=topology_entity)` required且只允许 `kind`、`entity_asset_id`、`entity_id`、`expected_source`、`flip`；`expected_source` 必须是 entity中exact `model_output` 或 `model_topology` source record。Vertex target强制 `flip=false`。
- `ConnectorBindingSpec.source_model` 只允许 `graph_id`、`model_schema_version`、`artifact_hash`；`source_scene` 只允许 `scene_id`、`revision`。Top-level只允许第 14.4 节示例中的九个 fields，全部 required，其中 `name` required-nullable。
- `ScenePresentationSpec` 的六个 top-level fields全部 required：`schema_version`、`presentation_id`、`source_scene_id`、`appearances`、`node_overrides`、`cameras`。其 nested exact records由第 12.4 节定义。
- `SceneNode.order` 是 non-negative integer；每个 root和每组 siblings分别从 0连续编号。Boolean fields必须是 JSON boolean，不能接受 0/1 coercion。

所有 JSON integer，包括 byte length、output slot、order、count、ordinal、range和GLB integer metadata，都必须位于 `[0, 9007199254740991]`；具体resource budget通常更小。Python与TypeScript validator不得接受会在JavaScript `Number`中丢失精度的integer。Float fields遵循finite binary64/JCS规则。

Phase A必须提交五个structural JSON Schema 2020-12 files：`scene-1.0.schema.json`、`entities-1.0.schema.json`、`presentation-1.0.schema.json`、`connector-binding-1.0.schema.json`和`normalized-product-1.schema.json`。JSON Schema不能表达JCS bytes、duplicate keys、hashes、ordering、cross-file references、cycles、ZIP或GLB rules，因此它不是完整validity authority。Phase A还必须提交normative`scene-1.0-rules.json`：每条semantic/package rule有stable lower-snake-case ID、applicable artifact、evaluation phase、JSON Pointer policy和precedence；Python/TypeScript validators必须按phase及rule ID的unsigned UTF-8 byte order报告第一个error。五个schemas、rule registry、两个profile specs及其hash-linked pseudocode、golden boundary/malformed corpus和exact JCS/GLB/ZIP vectors共同构成freeze source of truth。本文示例不得替代它们；全部cross-language tests通过后才能把状态从`Proposed`改为`Frozen`。

### 7.3 坐标与单位

Scene Schema 1.0 固定：

- 右手坐标系。
- `+Z` 为 up axis。
- 默认长度单位为 `mm`。
- Node transform 必须是 rigid transform，第一阶段不支持 scale、shear 或 reflection。

Scene hierarchy 和 bounds 使用上述 CAD scene coordinates。GLB asset 必须保持标准 glTF 2.0 坐标约定：右手、`+Y` up、线性单位为 meter。Compiler 使用固定转换将 CAD local points 写入 GLB：

```text
gltf_m = (cad_x_mm, cad_z_mm, -cad_y_mm) / 1000
```

每个 geometry/edge asset manifest 显式保存同一固定 `asset_to_scene` affine transform，将 GLB meter coordinates 转回 CAD scene millimeters：

```text
cad_mm = (1000 * gltf_x_m, -1000 * gltf_z_m, 1000 * gltf_y_m)
```

`asset_to_scene` 允许 fixed unit scale，因此不属于 Scene Node 的 rigid transform。Manifest 中的 16 个数字按 row-major、column-vector convention 解释。Renderer 的顺序必须是 `node_world_transform * asset_to_scene * asset_position`。不能把非标准 mm/`+Z` buffer 标记为 `model/gltf-binary`，也不能同时对 mesh 和 scene root 重复做 axis conversion。

### 7.4 Transform 表示

为避免 matrix、quaternion 和 axes 三套表示互相不一致，Scene 1.0 只使用一种 canonical rigid transform：

```json
{
  "origin": [0.0, 0.0, 0.0],
  "x_axis": [1.0, 0.0, 0.0],
  "y_axis": [0.0, 1.0, 0.0],
  "z_axis": [0.0, 0.0, 1.0]
}
```

Validator 必须检查：

- 所有数字 finite。
- 每个 axis 为单位向量。
- axes 两两正交。
- `z_axis` 与 `cross(x_axis, y_axis)` 一致。
- transform 是 parent-relative，不是重复保存的 world transform。

Base numeric profile固定：axis norm error、pairwise dot absolute value和cross-product component error都必须`<= 1e-12`。所有scene-coordinate point/origin/bounds components必须位于`[-1e12, 1e12]` mm；所有GLB float32 values必须finite。Bounds containment和derived frame composition使用`epsilon_mm = max(1e-9, 1e-12 * max(1, max_abs_coordinate))`；方向/axis比较仍使用`1e-12`。Non-negative length/area/volume不能通过epsilon接受负数。Validator不得使用平台默认`isclose`或随模型大小任意变化的hidden tolerance。

Renderer 可以在加载时派生 4x4 matrix。World transform 永远由 hierarchy composition 派生，不进入 canonical scene JSON。

## 8. Definition 与 Instance 模型

### 8.1 Definition

Definition 表示可复用的 product 或 geometry definition：

```json
{
  "definition_id": "definition/main/part/input-shaft",
  "kind": "part",
  "name": "Input Shaft",
  "geometry_asset_id": "sha256:...",
  "edge_asset_id": "sha256:...",
  "entity_asset_id": "sha256:...",
  "appearance_id": "appearance/evaluated/0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "source": {
    "kind": "product_model",
    "root_id": "main",
    "semantic_type": "Part",
    "semantic_id": "input-shaft",
    "graph_id": "gearbox",
    "node_id": "node_...",
    "output_slot": 0
  },
  "sdk_metadata": {}
}
```

支持的 `kind` 初始包括：

- `part`
- `assembly`
- `shape`

Assembly definition 通常没有 `geometry_asset_id`，其可见内容来自 descendant part instances。Standalone captured `Solid` 或 `Compound` 使用 `shape` definition。

Definition asset conditions 是：`part` 和 renderable `shape` 必须同时包含 `geometry_asset_id`、`edge_asset_id`、`entity_asset_id`、`appearance_id`。`assembly` 必须省略全部四个 asset/appearance refs，其可见内容只来自 descendants。每个 geometry/entity/edge ref 必须存在并形成一致的 definition-local triple；manifest 中不允许 unreferenced asset records。Base 1.0 不表达 generic group、intentionally non-renderable Part/Shape 或 shaded-only profile；这些需求以后通过 explicit capability 引入。

Definition `source` variants 的 exact fields 为：

- `kind=product_model`：required `kind`、`root_id`、`semantic_type`、`semantic_id`、`graph_id`、`node_id`、`output_slot`。`semantic_type` 只允许 `Part` 或 `Assembly`，并分别要求 definition `kind=part` 或 `kind=assembly`。
- `kind=product_manual`：required且只允许 `kind`、`root_id`、`semantic_type`、`semantic_id`；只允许 scene source `kind=manual`，不参与 model/DAG provenance。
- `kind=model_output`：required `kind`、`root_id`、`graph_id`、`node_id`、`output_slot`。
- `kind=imported`：required `kind`、`root_id`、`source_element_id`。
- `kind=manual`：required `kind`、`root_id`、`source_id`。

Top-level/source compatibility固定：

| Scene `source.kind` | Definition source | Entity source | Connector source | Node source |
| --- | --- | --- | --- | --- |
| `model` | `product_model` or `model_output` | `model_output` or proven `model_topology` | `model_operation` | `product_occurrence` or `shape_root` |
| `imported` | `imported` | `imported_primitive` or `unbound` | `null` | `shape_root` |
| `manual` | `product_manual` or `manual` | `unbound` | `manual` | `product_occurrence` or `shape_root` |

Base 1.0不允许一份scene混合不同行的provenance variants。Imported/manual entities可用于selection/inspection但`connector_binding_status`不能是`supported`。

Definition/node/source compatibility还必须满足以下exact matrix：

- `product_model`只用于`kind=part|assembly`，`semantic_type`必须分别为`Part|Assembly`；top-level source必须是`model`，nested `graph_id`必须等于top-level `source.graph_id`。
- `product_manual`只用于`kind=part|assembly`且`semantic_type`同样匹配；top-level source必须是`manual`。
- `model_output`只用于`kind=shape`且top-level source必须是`model`，nested `graph_id`必须等于top-level `source.graph_id`。
- `imported`只用于`kind=shape`且top-level source必须是`imported`；`source_element_id`必须等于对应`SceneRoot.source_element_id`。Imported scene固定`connectors=[]`。
- `manual`只用于`kind=shape`且top-level source必须是`manual`；nested `source_id`必须exact等于top-level `SceneSource.source_id`。
- `product_occurrence` node只能引用同`root_id`的`part|assembly` definition，其source必须是对应top-level row的`product_model|product_manual`。`shape_root` node只能引用同`root_id`的`shape` definition，其source必须是`model_output|imported|manual`。
- 每个node source、referenced definition source和derived structural IDs中的`root_id`必须相同。Model definition/entity/connector records中的每个nested `graph_id`必须等于top-level model graph ID；manual definition/connector nested `source_id`必须等于top-level manual source ID。

`sdk_metadata`保存definition owner的JSON-safe evaluated metadata。Part/Assembly owner metadata按第10.2节projection policy处理。Shape-level metadata通常不放在definition record，而放在entity snapshot的owning solid/entity record，避免definition与topology sidecar两份cache分歧。唯一例外是flattened Compound root：Compound自身不是Base entity kind，因此其projected Compound-level tags和metadata存入Shape definition`sdk_metadata`的exact keys`compound_tags`和`compound_metadata`；child Solid metadata仍留在entity records。两个keys在non-Compound definition中禁止。

### 8.2 Scene Node

Scene node 表示 hierarchy 中的一次 occurrence：

```json
{
  "node_id": "instance/main/stage1/input-shaft",
  "parent_node_id": "instance/main/stage1",
  "order": 3,
  "definition_id": "definition/main/part/input-shaft",
  "name": "Input Shaft Instance",
  "transform": {
    "origin": [0.0, 0.0, 18.0],
    "x_axis": [1.0, 0.0, 0.0],
    "y_axis": [0.0, 1.0, 0.0],
    "z_axis": [0.0, 0.0, 1.0]
  },
  "visible": true,
  "selectable": true,
  "appearance_override_id": null,
  "source": {
    "kind": "product_occurrence",
    "root_id": "main",
    "component_path": ["stage1", "input-shaft"]
  },
  "sdk_metadata": {}
}
```

Scene 只保存 `parent_node_id`，不同时保存 mutable `children` 数组，避免 parent/children 两份结构产生分歧。Sibling 显示顺序通过 `order` 显式保存。Root node 的 `parent_node_id` 为 `null`。

Node hierarchy 必须：

- 无环。
- 每个 non-root parent 存在。
- `node_id` 全局唯一。
- 每个 referenced definition 存在。
- 同一个 parent 下 `order` 不重复。

Scene 1.0 node 是 product/shape occurrence，必须引用 definition。Camera 和 light 不伪装成 product node，使用各自 record 中的 parent-relative transform。

Canonical `node.visible` 和 `node.selectable` 向 descendants传播：`effective_visible = node.visible && all_ancestor_visible`，`effective_selectable = node.selectable && all_ancestor_selectable && effective_visible`。Workspace hide/isolate在 canonical effective visibility之后叠加且不写回 scene。`appearance_override_id` 不继承，只影响该 node自己引用的 renderable definition；assembly node的 override必须为 `null`。

Node `source` variants 的 exact fields 为：

- `kind=product_occurrence`：required且只允许`kind`、`root_id`、`component_path`。Root occurrence的`component_path=[]`。
- `kind=shape_root`：required `kind`、`root_id`。

Product occurrence identity必须完全派生：`node_id`等于`instance/<root_id>`追加每个encoded component path segment；parent的component path必须恰为child path去掉最后一段，且`parent_node_id`等于其derived ID。Root occurrence的`parent_node_id=null`、`order`等于roots按`root_id` unsigned UTF-8 byte order排序后的ordinal。每组child `order`来自owner Assembly declaration order并从0连续编号。`visible=true`、`selectable=true`、`appearance_override_id=null`是没有presentation override时的exact defaults。Definition `name`等于owner Part/Assembly nullable name，Shape definition name固定`null`。Root Product occurrence `name`等于root Part/Assembly name；descendant occurrence先使用nullable`Component.name`，为null时使用referenced Part/Assembly name，仍缺失则为null；Shape root occurrence name固定`null`。Compiler不合成display label。

Root occurrence `instance/<root_id>.transform`必须exact等于resolved `SceneRoot.transform`；它是root-local frame到scene frame的唯一serialized placement。每个descendant occurrence的`transform`只保存其owner Assembly中parent-relative Component placement，不预乘root或ancestor transforms。World transform按第7.4节从root到leaf依次composition。Standalone Shape root使用相同root transform rule。

`sdk_metadata` 是 occurrence-level evaluated metadata。当前 `Component` API 没有 metadata hook，因此 product occurrences 输出 `{}`；保留该 required field 是为了让 component inspector 与未来 occurrence metadata extension 有稳定位置，不能把 definition metadata复制到这里。

### 8.3 Repeated Instances

同一个 `Part` 被多个 `Component` 引用时：

- 只生成一个 definition。
- 只生成一个 geometry asset。
- 为每个 component path 生成独立 scene node。
- 每个 node 保存自己的 transform、visibility 和 selection identity。

Nested repeated assembly 可以展开为多组 occurrence nodes，但 descendant part nodes 继续引用相同 part definition 和 geometry asset。

## 9. Geometry Asset Contract

### 9.1 Render Mesh 不等于 Collision Mesh

当前 private `TriMesh` 可以作为 Scene Compiler 的算法起点，但不应直接公开。需要新增独立的 triangle `RenderMesh` 和 line `RenderEdgeMesh` contract，原因包括：

- Collision mesh 只需要 positions 和 triangles。
- Triangle render mesh 需要 normals 和 face groups；edge overlay 需要独立 line buffer。
- Picking 需要 source entity ranges。
- Render asset 需要稳定 binary encoding 和 content hash。
- 后续 LOD、compression 和 quantization 不应影响 collision verifier。

推荐的内部不可变类型：

```python
@dataclass(frozen=True)
class RenderMesh:
    positions: np.ndarray
    normals: np.ndarray
    indices: np.ndarray
    face_groups: tuple[RenderFaceGroup, ...]
    bounds: Bounds3
    linear_tolerance: float
    angular_tolerance: float

@dataclass(frozen=True)
class RenderEdgeMesh:
    positions: np.ndarray
    indices: np.ndarray
    edge_groups: tuple[RenderEdgeGroup, ...]
    bounds: Bounds3
    linear_tolerance: float
```

### 9.2 Geometry Asset Manifest

```json
{
  "asset_id": "sha256:...",
  "uri": "geometry/sha256-....glb",
  "media_type": "model/gltf-binary",
  "byte_length": 123456,
  "content_hash": "sha256:...",
  "scene_local_bounds": {
    "min": [-10.0, -10.0, 0.0],
    "max": [10.0, 10.0, 50.0]
  },
  "asset_to_scene": [
    1000.0, 0.0, 0.0, 0.0,
    0.0, 0.0, -1000.0, 0.0,
    0.0, 1000.0, 0.0, 0.0,
    0.0, 0.0, 0.0, 1.0
  ],
  "tessellation": {
    "linear_tolerance": 0.35,
    "angular_tolerance": 0.22
  }
}
```

`asset_id` 与 `content_hash` 第一阶段相同，均为 deterministic GLB bytes 的 SHA-256。保留两个字段是为了将来支持 logical asset identity，但第一阶段禁止二者不一致。Geometry asset 不引用 entity asset，也不保存 graph/topology provenance；同一 geometry bytes 可以被不同 model/source definitions 复用。Geometry URI 必须是 `geometry/sha256-<hex>.glb`，其中 hex 与 ID 相同。

`scene_local_bounds`不是pre-quantization kernel bounds；它必须从GLB POSITION accessor中的canonical float32 values直接应用`asset_to_scene`映射到scene coordinates后逐分量计算，即`cad_mm=(1000*x,-1000*z,1000*y)`。Package validator从validated immutable GLB bytes重复该计算并要求JCS numeric value exact相等。Edge asset采用相同规则。Entity properties中的kernel-evaluated bounds是另一份精度更高的CAD evidence，不要求与render bounds bitwise相等。

### 9.3 GLB 使用范围

第一阶段 triangle GLB 只承担 appearance-neutral binary render geometry：

- positions
- normals
- indices

Scene hierarchy、product provenance、CAD topology identity 和 viewer annotations 不交给标准 GLB scene graph 管理。这些内容由 `scene.json` 和 entity snapshot sidecar 管理。

原因是：

- Scene hierarchy 需要 product/component path identity。
- 同一 geometry asset 需要被多个 scene node 实例化。
- Face-level picking 需要 graph/topology provenance。
- CAD-specific metadata 不应被塞入大量不受约束的 glTF `extras`。

Scene 1.0 triangle GLB profile 必须满足：

- 使用标准 glTF 2.0 meter、右手、`+Y` up coordinates。
- 恰好一个 scene、一个 identity node、一个 mesh 和一个 `TRIANGLES` primitive。
- Primitive 使用一个 `POSITION`、一个 `NORMAL` 和一个 index accessor。
- Index accessor 使用 unsigned 16-bit 或 unsigned 32-bit scalar。
- 不包含 glTF materials；definition/instance appearance 由 scene manifest 绑定。
- 不包含 images、textures、animations、skins、morph targets、cameras、lights、sparse accessors 或 nested URI。
- 只允许一个 GLB BIN-backed buffer，`buffer.uri` 必须 absent。
- 不允许 `extras`、unknown extensions、Draco 或 Meshopt。
- Face range 使用 primitive-local index ordinal；Scene 1.0 固定 `mesh_index=0`、`primitive_index=0`。

一个 primitive 的限制使 face ranges 存在唯一 global index-ordinal space，也保证 appearance-only change 不改变 GLB bytes。未来多 material slot 必须在新 capability 中定义 external primitive-slot mapping，不能偷偷向同一 1.0 asset 增加 primitives。

Triangle GLB 的 JSON object 必须等价于以下 exact closed skeleton；除替换 `<...>` values外不得增加/省略 fields。引号中的angle-bracket tokens只是本文metavariable，实际`count`、`byteLength`、`byteOffset`、`componentType`和bounds components必须是JSON integer/number，绝不能序列化为string：

```json
{
  "accessors": [
    {"bufferView": 0, "componentType": 5126, "count": "<vertex_count>", "max": ["<x>", "<y>", "<z>"], "min": ["<x>", "<y>", "<z>"], "type": "VEC3"},
    {"bufferView": 1, "componentType": 5126, "count": "<vertex_count>", "type": "VEC3"},
    {"bufferView": 2, "componentType": "<5123-or-5125>", "count": "<index_count>", "type": "SCALAR"}
  ],
  "asset": {"generator": "SimpleCAD Scene GLB Profile 1", "version": "2.0"},
  "bufferViews": [
    {"buffer": 0, "byteLength": "<12*vertex_count>", "byteOffset": 0, "target": 34962},
    {"buffer": 0, "byteLength": "<12*vertex_count>", "byteOffset": "<normal_offset>", "target": 34962},
    {"buffer": 0, "byteLength": "<index_bytes>", "byteOffset": "<index_offset>", "target": 34963}
  ],
  "buffers": [{"byteLength": "<unpadded_bin_bytes>"}],
  "meshes": [{"primitives": [{"attributes": {"NORMAL": 1, "POSITION": 0}, "indices": 2, "mode": 4}]}],
  "nodes": [{"mesh": 0}],
  "scene": 0,
  "scenes": [{"nodes": [0]}]
}
```

Line GLB 使用同一 exact fields，但只有两个 accessors/bufferViews：accessor 0 是 POSITION float32 VEC3并包含 min/max，accessor 1 是 index SCALAR；primitive恰为 `{"attributes":{"POSITION":0},"indices":1,"mode":1}`。`bufferViews[0].target=34962`、`bufferViews[1].target=34963`。不存在 NORMAL accessor。

BIN layout 对 triangle 固定为 tightly packed position float32 triples、normal float32 triples、indices；line固定为 positions、indices。每段 start 4-byte aligned，段间和最终 BIN padding为 zero。`byteOffset` 即上述 prefix加alignment；即使为 0也必须按 skeleton输出。`buffer.byteLength` 是最后一个有效byte后的 unpadded length；GLB BIN chunk length向上4-byte对齐。Accessor不输出 `byteOffset`、`normalized`、`name`、`sparse`或其他 optional fields；bufferView不输出 `byteStride`或`name`。POSITION min/max从写入buffer的 canonical glTF float32 values逐分量计算并以JCS number输出；normal/index accessors省略min/max。

Index component type在`vertex_count <= 65536`时固定5123，否则5125；所有vertices必须至少被一个index引用，所以该条件等价于`max_index <= 65535`。空geometry禁止，因此不用5121。JSON chunk是上述object的RFC 8785 JCS UTF-8 bytes，尾部只用ASCII space补到4-byte；BIN只用zero补齐。GLB header和chunk headers按glTF 2.0 little-endian exact constants写出，total length必须精确等于两chunks。任何timestamp、path、toolchain version或random value都禁止进入GLB；toolchain只在scene manifest`generator`中。

第10.4节冻结vertex/entity/group ordering和normal policy。如果OCP tessellation只保证集合等价，writer必须先执行这些规范化规则；不能把偶然的Python/OCP iteration order作为contract。Phase A必须发布triangle与line各至少一个normative exact-byte golden GLB fixture及其SHA-256，Python和TypeScript preflight都必须接受；Phase B writer必须逐byte重现这些fixtures。

### 9.4 Normals

当前 tessellator 没有公开 normals。Scene Compiler 必须定义明确策略：

1. 优先读取 kernel triangulation normals。
2. 无可用 normals 时，根据 oriented triangle 计算 face normals。
3. 跨 CAD face 默认不平滑，避免圆角边界或 sharp edge 被错误平滑。
4. 同一 CAD face 内也不做跨 triangle averaging；使用第 10.4 节规定的 kernel corner normal 或 oriented triangle fallback。
5. 所有 normals 必须 finite 且 normalized。

Position转换为canonical glTF float32后，任意两个corner bitwise相同或profile binary32 cross product恰为zero的triangle作为collapsed tessellation丢弃。Edge endpoint转换后bitwise相同的segment同样丢弃。丢弃发生在canonical sort和group range构造前；remaining index stream不得包含未引用vertex。若因此使某个face为空，Base 1.0 compilation失败；edge为空时按第10.2节标记`render_status=degenerate`并省略其group。Compiler不得输出NaN normal、zero normal、degenerate primitive或zero-count accessor来隐式降级。

### 9.5 CAD Edge Overlay

CAD Viewer 不能用 triangle boundary 代替 CAD edge。Triangle boundary 会显示 tessellation 内部对角线，也无法保持 analytic edge 语义。

需要单独对 BRep edges 做曲线离散化，保存：

- Edge polyline positions。
- Source edge reference。
- Boundary/seam 可选分类。
- Local bounds。

Edge asset 也使用 content-addressed GLB，但采用独立 Scene 1.0 line profile：恰好一个 `LINES` primitive，positions 使用 standard glTF coordinates，indices 将每条 curve 离散为 segment pairs。每个 edge group 引用同一 primitive 中连续、偶数长度的 index range。Viewer 使用 line pass 绘制 edge overlay。Silhouette 可以由 GPU 派生，但不能替代完整 CAD edge asset。

Edge asset manifest 与 geometry asset manifest 使用相同的 `asset_id`、media type、byte length、content hash、scene-local bounds 和 `asset_to_scene` 字段；其 URI 固定为 `edges/sha256-<hex>.glb`，`tessellation` 只有 `linear_tolerance`。Base 1.0 每个 renderable definition 都必须引用 edge asset；普通 shaded-only scene 需要后续单独 profile，不能通过省略 Base required asset 隐式降级。

## 10. Evaluated Entity Snapshot、Picking 与 Provenance

### 10.1 Selection Intent 与解析

Viewer MVP 支持五种显式 selection intent：

1. `component`：选择一个 scene occurrence，identity 是 `scene_node_id`。
2. `solid`：从命中的 face 解析其 owning solid entity。
3. `face`：从 triangle primitive index 解析 face range。
4. `edge`：从 CAD edge line segment 解析 edge range。
5. `vertex`：对 entity snapshot 中的 vertex point 建立 runtime point-picking buffer，并使用 screen-space threshold 命中。

Viewer 不从 triangle adjacency 猜测 CAD face/edge/vertex。一次 viewport hit 按以下顺序解析：GPU draw/instance -> scene occurrence -> definition -> entity asset -> render range -> entity record -> source graph/topology provenance。Solid selection 使用 face record 的 `parent_entity_ids` 找到唯一 owning solid；vertex selection 的 point buffer只用于 picking/highlight，不作为默认可见模型内容。

`component` 与 `solid` 不是同义词。一个 component occurrence 可以引用 assembly definition而没有 solid，也可以在后续 multi-body capability 中拥有多个 solids。Repeated instances 共享同一 entity asset，但通过不同 `scene_node_id` 保持 occurrence identity。

### 10.2 Entity Snapshot Asset

Scene manifest 中的 entity asset record 只保存 transport metadata：

```json
{
  "entity_asset_id": "sha256:...",
  "uri": "entities/sha256-....json",
  "media_type": "application/vnd.simplecad.entities+json",
  "byte_length": 34567,
  "content_hash": "sha256:..."
}
```

`entity_asset_id` 与 `content_hash` 在 Scene 1.0 中相同。Payload 本身不包含 `entity_asset_id`，避免 self-hash cycle；其 JCS bytes 定义 content hash。一个 geometry asset 可以对应多个 source/provenance/metadata 不同的 entity assets。

Entity URI 必须是 `entities/sha256-<hex>.json`，其中 hex 与 ID 相同。Definition 引用 geometry 时 entity asset mandatory，不能用 missing sidecar 表示“只看 mesh”；不需要 metadata/picking 的客户端可以选择不下载，但 package 仍必须完整包含并验证它。

```json
{
  "schema_version": "1.0",
  "definition_id": "definition/main/part/input-shaft",
  "geometry_asset_id": "sha256:...",
  "edge_asset_id": "sha256:...",
  "geometry_engine": {
    "name": "OpenCascade",
    "version": "7.8.1",
    "profile": "ocp-evaluated-properties-1"
  },
  "entities": [
    {
      "entity_id": "entity/solid/0",
      "kind": "solid",
      "parent_entity_ids": [],
      "child_entity_ids": ["entity/face/0"],
      "source": {
        "kind": "model_output",
        "graph_id": "gearbox",
        "node_id": "node_...",
        "output_slot": 0
      },
      "geometry": {"type": "brep_solid"},
      "properties": {
        "quality": "kernel_evaluated",
        "bounds": {"min": [-10.0, -10.0, 0.0], "max": [10.0, 10.0, 50.0]},
        "volume": 12500.0,
        "surface_area": 4100.0,
        "centroid": [0.0, 0.0, 25.0]
      },
      "sdk_connector_frame": null,
      "render_status": "rendered",
      "connector_binding_status": "not_applicable",
      "semantic_binding_ids": [],
      "evaluated_tags": ["solid.body"],
      "sdk_metadata": {}
    },
    {
      "entity_id": "entity/face/0",
      "kind": "face",
      "parent_entity_ids": ["entity/solid/0"],
      "child_entity_ids": ["entity/edge/0"],
      "source": {
        "kind": "model_output",
        "graph_id": "gearbox",
        "node_id": "node_...",
        "output_slot": 0
      },
      "geometry": {
        "type": "plane",
        "origin": [0.0, 0.0, 50.0],
        "normal": [0.0, 0.0, 1.0],
        "x_direction": [1.0, 0.0, 0.0]
      },
      "properties": {
        "quality": "kernel_evaluated",
        "bounds": {"min": [-10.0, -10.0, 50.0], "max": [10.0, 10.0, 50.0]},
        "area": 400.0,
        "centroid": [0.0, 0.0, 50.0],
        "orientation": "forward"
      },
      "sdk_connector_frame": {
        "origin": [0.0, 0.0, 50.0],
        "x_axis": [1.0, 0.0, 0.0],
        "y_axis": [0.0, 1.0, 0.0],
        "z_axis": [0.0, 0.0, 1.0]
      },
      "render_status": "rendered",
      "connector_binding_status": "supported",
      "semantic_binding_ids": ["binding-..."],
      "evaluated_tags": ["role.mounting_surface"],
      "sdk_metadata": {"manufacturing": {"finish": "ground"}}
    },
    {
      "entity_id": "entity/edge/0",
      "kind": "edge",
      "parent_entity_ids": ["entity/face/0"],
      "child_entity_ids": ["entity/vertex/0", "entity/vertex/1"],
      "source": {"kind": "model_output", "graph_id": "gearbox", "node_id": "node_...", "output_slot": 0},
      "geometry": {"type": "line", "origin": [-10.0, 0.0, 50.0], "direction": [1.0, 0.0, 0.0]},
      "properties": {
        "quality": "kernel_evaluated",
        "bounds": {"min": [-10.0, 0.0, 50.0], "max": [10.0, 0.0, 50.0]},
        "length": 20.0,
        "centroid": [0.0, 0.0, 50.0]
      },
      "sdk_connector_frame": {
        "origin": [0.0, 0.0, 50.0],
        "x_axis": [0.0, 1.0, 0.0],
        "y_axis": [0.0, 0.0, 1.0],
        "z_axis": [1.0, 0.0, 0.0]
      },
      "render_status": "rendered",
      "connector_binding_status": "supported",
      "semantic_binding_ids": [],
      "evaluated_tags": [],
      "sdk_metadata": {}
    },
    {
      "entity_id": "entity/vertex/0",
      "kind": "vertex",
      "parent_entity_ids": ["entity/edge/0"],
      "child_entity_ids": [],
      "source": {"kind": "model_output", "graph_id": "gearbox", "node_id": "node_...", "output_slot": 0},
      "geometry": {"type": "point", "position": [-10.0, 0.0, 50.0]},
      "properties": {
        "quality": "kernel_evaluated",
        "bounds": {"min": [-10.0, 0.0, 50.0], "max": [-10.0, 0.0, 50.0]},
        "position": [-10.0, 0.0, 50.0]
      },
      "sdk_connector_frame": {
        "origin": [-10.0, 0.0, 50.0],
        "x_axis": [1.0, 0.0, 0.0],
        "y_axis": [0.0, 1.0, 0.0],
        "z_axis": [0.0, 0.0, 1.0]
      },
      "render_status": "rendered",
      "connector_binding_status": "supported",
      "semantic_binding_ids": [],
      "evaluated_tags": [],
      "sdk_metadata": {}
    },
    {
      "entity_id": "entity/vertex/1",
      "kind": "vertex",
      "parent_entity_ids": ["entity/edge/0"],
      "child_entity_ids": [],
      "source": {"kind": "model_output", "graph_id": "gearbox", "node_id": "node_...", "output_slot": 0},
      "geometry": {"type": "point", "position": [10.0, 0.0, 50.0]},
      "properties": {
        "quality": "kernel_evaluated",
        "bounds": {"min": [10.0, 0.0, 50.0], "max": [10.0, 0.0, 50.0]},
        "position": [10.0, 0.0, 50.0]
      },
      "sdk_connector_frame": {
        "origin": [10.0, 0.0, 50.0],
        "x_axis": [1.0, 0.0, 0.0],
        "y_axis": [0.0, 1.0, 0.0],
        "z_axis": [0.0, 0.0, 1.0]
      },
      "render_status": "rendered",
      "connector_binding_status": "supported",
      "semantic_binding_ids": [],
      "evaluated_tags": [],
      "sdk_metadata": {}
    }
  ],
  "face_groups": [
    {
      "group_id": 0,
      "entity_id": "entity/face/0",
      "mesh_index": 0,
      "primitive_index": 0,
      "first_index": 0,
      "index_count": 180
    }
  ],
  "edge_groups": [
    {
      "group_id": 0,
      "entity_id": "entity/edge/0",
      "mesh_index": 0,
      "primitive_index": 0,
      "first_index": 0,
      "index_count": 12
    }
  ]
}
```

Payload required fields 是 `schema_version`、`definition_id`、`geometry_asset_id`、`edge_asset_id`、`geometry_engine`、`entities`、`face_groups`、`edge_groups`。`geometry_engine` exact fields 是 `name`、`version`、`profile`；`name`固定为`OpenCascade`，`version`必须是exact kernel version且与manifest`generator.ocp_version`相同，不接受`7.x`。

每个entity required fields是`entity_id`、`kind`、`parent_entity_ids`、`child_entity_ids`、`source`、`geometry`、`properties`、`sdk_connector_frame`、`render_status`、`connector_binding_status`、`semantic_binding_ids`、`evaluated_tags`、`sdk_metadata`，不允许其他字段。`kind`只允许`solid`、`face`、`edge`、`vertex`。`entity_id`使用asset-local`entity/<kind>/<ordinal>`，ordinal grammar是`0|[1-9][0-9]*`；它只在`entity_asset_id` scope内唯一。Compiler必须按第10.4节deterministic profile生成ordinal，不得宣称该ordinal跨不同model revision durable。

Entity `source` 是 exact discriminated union：

- `kind=model_output`：required `kind`、`graph_id`、`node_id`、`output_slot`。它证明entity来自该evaluated operation output，但不声称model artifact包含该subshape的durable topology identity。
- `kind=model_topology`：required `kind`、`graph_id`、`node_id`、`output_slot`、`topology_kind`、`topo_id`。
- `kind=imported_primitive`：required `kind`、`source_element_id`。
- `kind=unbound`：只允许 `kind`。

Graph-backed evaluated BRep 的每个entity至少使用 `model_output`。该tuple是拥有整个definition BRep的shape output，通常是Part body source或standalone shape root；它不是随便选取的“最近operation”。只有exact source `model.json`自身包含能唯一关联该entity的topology record，且trusted compiler能把该record解析到当前evaluated subshape时，compiler才可把该entity升级为`model_topology`。`topology_kind`必须与entity kind对应为`SOLID`、`FACE`、`EDGE`或`VERTEX`，且`(graph_id,node_id,output_slot,topology_kind,topo_id)`必须能在artifact中exact查到。由OCP traversal counter、process-local map、shape hash或scene compiler临时分配的ID不得写成`topo_id`。同一definition asset可以混合两种model source variants，但不得把缺失evidence从相邻entity推断出来。`imported_primitive`和`unbound`不参与DAG cross-link或connector binding。

For imported roots，definition `source_element_id`来自`SceneRoot.source_element_id`。只有trusted importer还能提供exact source artifact内stable primitive mapping时，entity才使用对应`imported_primitive.source_element_id`；该ID不要求等于root element ID。没有这种evidence时entity必须使用`unbound`，不能从OCP traversal、canonical entity ordinal或geometry hash伪造imported primitive identity。

`geometry` 是 typed analytic-classification snapshot，不是可 replay BRep：solid 使用 `brep_solid`；vertex 使用 `point` + `position`；edge 使用 `line`、`circle`、`ellipse`、`bspline_curve` 或 `other_curve`；face 使用 `plane`、`cylinder`、`cone`、`sphere`、`torus`、`bspline_surface` 或 `other_surface`。每个 variant 只允许其数学定义所需字段；unsupported kernel detail 使用 `other_curve`/`other_surface` 的 required `engine_type`，不能把 opaque OCP object dump 进 JSON。Axis/direction vectors normalized，radii/lengths non-negative，所有坐标使用 definition-local scene coordinates 和 scene length unit。

Geometry variant exact fields：

| `type` | Required fields beyond `type` | Optional/nullable fields |
| --- | --- | --- |
| `brep_solid` | 无 | 无 |
| `point` | `position` | 无 |
| `line` | `origin`, `direction` | 无 |
| `circle` | `center`, `normal`, `x_direction`, `radius` | 无 |
| `ellipse` | `center`, `normal`, `x_direction`, `major_radius`, `minor_radius` | 无 |
| `bspline_curve` | `degree`, `rational`, `periodic`, `poles_count`, `knots_count` | 无 |
| `other_curve` | `engine_type` | 无 |
| `plane` | `origin`, `normal`, `x_direction` | 无 |
| `cylinder` | `origin`, `axis`, `x_direction`, `radius` | 无 |
| `cone` | `origin`, `axis`, `x_direction`, `reference_radius`, `semi_angle_degrees` | 无 |
| `sphere` | `center`, `axis`, `x_direction`, `radius` | 无 |
| `torus` | `center`, `axis`, `x_direction`, `major_radius`, `minor_radius` | 无 |
| `bspline_surface` | `u_degree`, `v_degree`, `u_rational`, `v_rational`, `u_periodic`, `v_periodic`, `u_poles_count`, `v_poles_count`, `u_knots_count`, `v_knots_count` | 无 |
| `other_surface` | `engine_type` | 无 |

Vector/point fields 是恰好三个 finite numbers。`degree` 和所有 `*_count` 是 non-negative integers；实际 B-spline validity 还必须满足 engine/profile 定义的 degree/pole/knot constraints。`major_radius >= minor_radius > 0`，其他 radius positive；cone semi-angle 必须落在 engine profile 允许的 open interval。Geometry record 不保存 trimmed parameter ranges、control points 或 full BRep，因此它是可查询分类/属性快照而不是 interchange geometry。

`properties`按`kind`固定：solid required`quality`、`bounds`、`volume`、`surface_area`、`centroid`；face required`quality`、`bounds`、`area`、`centroid`、`orientation`；edge required`quality`、`bounds`、`length`、`centroid`；vertex required`quality`、`bounds`、`position`。`quality`在Base 1.0固定为`kernel_evaluated`；face`orientation`只允许`forward`、`reversed`、`internal`、`external`。Edge orientation是face-use/coedge属性，不是deduplicated edge intrinsic property，Base 1.0不序列化它。这些值是指定engine/profile对evaluated BRep的快照，不保证仅凭mesh可重算。

`bounds` exact fields 是 `min`、`max`，二者都是 vec3 且逐轴 `min <= max`。Length、area、volume 分别使用 scene unit、scene unit squared、scene unit cubed；它们必须 non-negative。Centroid/position 必须落在 bounds 内，允许 validator 的 declared numeric tolerance。Base 1.0 不接受 record-specific arbitrary property bags；新增 engine properties必须升级 profile/schema 或使用 namespaced extension。

`sdk_connector_frame`是使用当前SDK selector/frame derivation对该entity预计算的unflipped definition-local rigid transform。`solid`必须为`null`；face和vertex必须是valid transform；edge在current SDK能取得non-zero start-to-end direction时是valid transform，否则为`null`。Closed edge的coincident endpoints不能使用arbitrary fallback伪造direction，因此其frame为`null`。Static Viewer只预览non-null frame。Vertex target的binding`flip`必须为`false`，UI不显示flip control。未来若新增deterministic tangent-based closed-edge frame，必须更换`geometry_engine.profile`。

`render_status`只允许`rendered`和`degenerate`。Solid、face和vertex固定`rendered`。Edge在canonical float32 filtering后至少有一个non-zero segment时为`rendered`，否则为`degenerate`；degenerate edge保留properties/adjacency/picking inspector identity，但没有edge group、line hit target或visible overlay。

`connector_binding_status`只允许`not_applicable`、`owner_not_part`、`source_not_model`、`frame_undefined`、`selector_ambiguous`、`selector_unstable`、`supported`。Solid固定`not_applicable`。Face/edge/vertex只有在owner是model-backed Part、source是`model_output`或`model_topology`、frame non-null、当前SDK生成的`geo_exact` selector在owner body全部同kind candidates中恰有一个score`<= 1e-4`且所有其他scores`> 1e-4`、并且clean replay后重新编译仍映射回同一canonical entity时才可标记`supported`。其余状态按上述优先顺序选择第一个适用reason。当前public resolver尚未拒绝ties，因此backend在advertise connector apply capability前必须增加同一unique-match validation；scene compiler不能仅因best candidate通过threshold就写`supported`。

拓扑adjacency必须闭合且满足exact cardinality：solid的parents必须为空、children必须是至少一个face；face必须恰好一个solid parent、children全部是至少一个edge；edge必须有一个或多个face parents、children是一个或两个vertices；vertex必须有一个或多个edge parents且children为空。每一条parent relation必须有reciprocal child relation。所有adjacency arrays按unsigned UTF-8 byte ordersort且无重复。Solid intent命中face后使用其唯一solid parent。Standalone wire/shell和shared-face compsolid不属于Base Scene 1.0 render root；遇到无法投影为上述manifold solid ownership的root必须显式失败，不能由unregistered extension绕过。

`semantic_binding_ids`和`evaluated_tags`是Semantic Binding Store对当前evaluated entity派生的只读cache。Compiler必须验证每个binding存在于exact source graph且runtime target确为该entity。Browser对`model_topology` entity还能把binding topology target与entity source做exact cross-check；对只有`model_output`的entity，browser只能验证binding ID、producer graph和schema存在，不能把cache误标为artifact-proven topology evidence。

`sdk_metadata`只投影evaluated metadata中不属于compiler/runtime internals的top-level keys。Base exclusion set固定为`graph`、`topo_ref`、`track`、`source_sketch`、`sketch_solve`、`sketch_promotion`以及所有以`_`开头的keys；这些值可能包含process-local topology IDs或runtime objects，必须省略而不是hash入entity identity。`geo`、`std.*`和其他non-reserved user keys保留。投影值必须是JSON object，递归允许null、boolean、string、finite number、array和string-keyed object；tuple规范化为array，未知Python/OCP value、bytes、set、non-string key和cycle必须使compilation失败并报告metadata path，不能静默`repr()`。Profile改变exclusion set必须更换profile ID。Object keys按JCS处理，metadata size计入package budgets。

Model-backed compilation只接受exact model artifact clean replay后的projected metadata。Compiler必须先replay exact model bytes，按root source tuple取得replayed values，再逐个比较caller runtime Part/Assembly/Material/Compound/Solid及其face/edge/vertex的projected tags/metadata与clean replay；任一不同以`model_runtime_metadata_unreplayable`失败。Connector metadata不在Scene 1.0 projection内。Canonical scene始终使用replayed projection，不使用无法由model artifact重建的runtime mutation。Manual/imported scenes可以投影其input metadata，因为其source identity不是replay promise。直到下述canonical operation实现并迁移stdlib，作者若需保存model metadata不能在build返回后调用unrecorded`set_metadata()`改变scene revision。

Replayable metadata operation contract固定为public keyword-only `set_model_metadata_rvalue(*, owner, key, value)`和graph op `set_model_metadata`。`owner`只允许`Solid|Compound|Part|Assembly|Material`；Face/Edge/Vertex和Connector metadata不在Base contract。`key`必须是non-empty Unicode string，不得以`_`开头或属于Base exclusion set，UTF-8长度不超过structural ID budget。`value`必须通过第10.2节JSON-safe normalization，normalized value连同`key`完整写入node params。Operation functional-copy owner及其metadata map，以normalized value replace同key的旧值并返回与input相同semantic owner type；不删除key、不原地修改input，output count固定1。Shape owner使用semantic clone保留BRep/tag/topology evidence，Product/Material owner使用immutable reconstruction保留all fields。Replay执行同一normalization/replacement且output lineage指向该node slot 0；Model Schema 2.0 exporter/importer/replay allowlist和translator capability registry必须注册exact op，未识别它时strict replay失败。Phase B迁移所有stdlib post-operation metadata writes到该API；old artifacts不会被悄悄升级，仍按runtime/replay mismatch fail closed。

Face/edge group record exact fields都是`group_id`、`entity_id`、`mesh_index`、`primitive_index`、`first_index`、`index_count`，不允许null或额外字段；除`entity_id`外的五个fields都必须是non-negative integers。`mesh_index=0`且`primitive_index=0`。Face groups与face entities一一对应，每个face恰有一个positive group。Edge groups只与`render_status=rendered`的edges一一对应，每个rendered edge恰有一个positive group；degenerate edge恰有zero groups。`group_id`在各自array中从0连续递增。Face groups必须按`first_index`排序、互不重叠，并精确partition triangle primitive的全部indices；每组`index_count`是3的倍数。Edge groups必须精确partition line primitive的全部indices；每组`index_count`是2的倍数。`first_index`和`index_count`是primitive index accessor的element ordinal，不是byte offset。Vertex没有serialized render range。任何face无法产生至少一个non-degenerate triangle时Base 1.0 compilation失败；degenerate edge不使整个solid失败。

### 10.3 Selection Identity

Entity selection 的完整 external identity 是：

```text
(scene_id, revision, scene_node_id, entity_asset_id, entity_id)
```

Component selection identity 是 `(scene_id, revision, scene_node_id)`。内部 scene/presentation references 不附加 scene/revision，使用 discriminated `SelectionRef`：

```json
{"kind": "component", "scene_node_id": "instance/main/stage1/input-shaft"}
```

```json
{
  "kind": "entity",
  "scene_node_id": "instance/main/stage1/input-shaft",
  "entity_asset_id": "sha256:...",
  "entity_id": "entity/face/0"
}
```

`scene_id` 和 `revision` 只在 workspace、API 或 command envelope 中附加，避免 canonical scene manifest self-reference。不能把 OCC hash、Python object ID、当前 process enumeration index 或 `topo_id` 单独作为 durable identity。跨 model regeneration 优先依赖 semantic binding/query intent；无法证明同一 target 时必须 invalidated，不能用 geometry-nearest 自动替换 critical selection。

当前Viewer显示的`UNIQUE QL SELECTOR`只是从sidecar中evaluated tags、analytic type、exact measure/center facts和source-output hints生成的便利draft，并且只在这些facts能隔离一个同kind entity时提供。它不属于上述selection identity，不是canonical feature-selection intent，也不能未经重新验证跨revision持久化或自动应用。

### 10.4 Deterministic Profile 1

Base 1.0 固定 `generator.profile="scene-1.0-ocp-glb-2"` 和 entity `geometry_engine.profile="ocp-evaluated-properties-1"`。这两个 profile 的 normative rules 是：

1. Phase A提交normative`scene-1.0-ocp-glb-2.profile.json`和`ocp-evaluated-properties-1.profile.json`。前者固定OCP meshing/discretization API、all flags、parallelism、normal/writer implementation和下面的numeric algorithm；后者固定analytic classification OCP APIs、location/orientation handling、axis conventions、B-spline constraints、engine type strings、property algorithms、metadata projection、selector scoring和connector frame tie-breaker。Prose中的“current SDK rule”不能替代这两个machine-readable profile和linked pseudocode。
2. `toolchain_hash` descriptor是closed JCS object，包含两个profile bytes hashes，以及SimpleCAD scene/compiler/product/selector modules、Python executable、OCP binding shared libraries和transitive native kernel libraries的SHA-256 records；records按logical name排序，绝对path、mtime和host name不进入descriptor。Hash是descriptor JCS bytes的SHA-256。Exact version fields只用于展示，不代替hash。
3. 所有subshape先消除location到definition-local coordinates。Edge wrapper在properties、discretization、selector和frame derivation前强制使用OCP `FORWARD` orientation；face orientation保留，因为每个face只有一个solid owner。Base 1.0拒绝被多个solids共享的face/compsolid topology，不靠traversal选择owner。Edge-face incidence可以many-to-many，但不保存coedge orientation。
4. Numeric primitive`f32(x)`固定为IEEE-754 binary32 round-to-nearest-ties-to-even，再把`0x80000000`改为`0x00000000`；overflow/non-finite失败。Binary32 boundary fixture使用exact input binary64 bit patterns。Cross product在binary64中按`p1=f64(a1*b1)`、`p2=f64(a2*b2)`、`c=f64(p1-p2)`逐项执行，禁止FMA；norm使用binary64 sum-of-squares fixed x/y/z order和correctly-rounded square root。Normalize后每component经`f32`一次，若result norm不在`[1-1e-6,1+1e-6]`则失败。Collapsed test使用converted positions的binary32 values提升到binary64后执行上述cross；cross三components bitwise为positive/negative zero即collapsed。Profile vectors覆盖subnormal、halfway tie、cancellation、overflow和negative zero。
5. 每个face先生成geometry-only canonical triangle block：不含entity ID/source/tags/metadata，包含sorted canonical `(position bits,normal bits)` vertices和oriented triangles。每个rendered edge生成geometry-only canonical segment block。`render_key=SHA-256(kind byte || block bytes)`。Triangle/line GLB按`(render_key, block bytes)`排列blocks；equal blocks顺序可交换且产生相同GLB bytes。Metadata、provenance、binding或tag-only change因此不能改变geometry/edge asset hash。
6. Triangle block中kernel corner normal可用时按profile读取并normalize；否则使用oriented triangle normal。禁止跨triangle/CAD face averaging。每个oriented triangle只允许cyclic rotation，不允许reversal；选择index triple lexicographic最小的cyclic rotation，再sort。Edge block中endpoint indices取`(min,max)`，segment pairs sort并deduplicate；different CAD edges即使geometry相同仍拥有different sidecar groups，但重复的block bytes不改变GLB block stream。
7. Entity canonical labeling先以`kind + geometry/properties/source/frame/status/bindings/tags/projected metadata + render_key`的JCS bytes hash建立partition，再使用sorted parent/child partition-label multisets反复refine到stable。仍有non-singleton cells时只在每个cell内执行lexicographic individualization/backtracking；全sidecar最多探索1,000,000 states，超出则compilation以`entity_canonicalization_budget_exceeded`失败。该有界algorithm和tie comparator在profile pseudocode中逐步固定，不允许实现选择另一graph canonicalizer。按canonical permutation和kind order`solid < face < edge < vertex`分配IDs。
8. Equal render blocks的range slots按canonical entity ID分配；因此entity sidecar mapping确定，但GLB bytes不依赖entity canonical order。Face/edge groups按`first_index`输出，entities按entity ID输出；all set-like entity arrays按unsigned UTF-8 byte ordersort。GLB array/buffer order遵循第9.3节。
9. Default appearance exact values是：`name=null`、`source=null`、`base_color=[0.72,0.75,0.78,1.0]`、`metallic=0.0`、`roughness=0.55`、`alpha_mode="opaque"`、`double_sided=false`、`edge_color=[0.08,0.09,0.1,1.0]`、`sdk_metadata={}`。
10. Phase A提交closed`normalized-product-1.schema.json`。Part record包含body source identity、name、material完整JSON-safe record、declaration-order connector records和projected Part metadata；Assembly record包含name、declaration-order component records、connectors、constraints、grounded IDs和projected metadata。每个component record exact包含`component_id`、nullable`name`、definition ref和local placement，declaration order保留。Connector records不含runtime `_metadata`。Compiler比较其JCS bytes；任一field不同即typed semantic ID collision。禁止用mesh bytes或“至少相同”heuristic判定equivalence。

Profile任何normative rule变化都必须使用新profile ID并造成cache miss。Characterization tests必须覆盖symmetric entity、bounded canonicalization failure、reversed kernel traversal、negative zero、normal fallback、closed/degenerate edge、shared-face rejection和duplicate geometry with different metadata/provenance。

## 11. Appearance

Product `Material` 当前同时包含物理属性和基础 RGB。Scene 不应直接把物理 material schema 扩展成 renderer shader schema，而应新增 `Appearance`：

```json
{
  "appearance_id": "appearance/evaluated/012345...",
  "name": "Steel",
  "source": {
    "kind": "product_material",
    "root_id": "main",
    "material_id": "steel"
  },
  "base_color": [0.55, 0.58, 0.62, 1.0],
  "metallic": 0.0,
  "roughness": 0.55,
  "alpha_mode": "opaque",
  "double_sided": false,
  "edge_color": [0.08, 0.09, 0.1, 1.0],
  "sdk_metadata": {}
}
```

`appearance_id` 最后一段是去掉 `appearance_id` 字段后，对完整 JCS Appearance record 求 SHA-256 的 lowercase hex。由于 source scope 也参与 hash，不同 roots 中同名但不同来源/内容的 materials 不会碰撞。完全相同的 source-scoped appearance record 才能复用一个 ID。

Appearance `source` nullable；non-null variants 是：`kind=product_material` required `kind`、`root_id`、`material_id`，`kind=presentation` required `kind`、`presentation_id`、`appearance_name`。`product_material`只允许top-level `model|manual` scene，`root_id`必须匹配至少一个使用该Material的Part definition root；imported scene不能包含它。`presentation`只在`presentation_source`存在时允许，`presentation_id`必须与其相等且`appearance_name`必须解析到exact authoring record。Compiler neutral default使用`source=null`，其complete record仍通过content hash获得稳定identity。`name`可以为null。`sdk_metadata`保存source Product `Material`的JSON-safe metadata；presentation/default appearance使用`{}`，不把Part metadata复制到material inspector。

`base_color`和`edge_color`恰好四个`[0,1]`values，按sRGB color + linear alpha编码；renderer在lighting calculation前转换RGB到linear。`metallic`、`roughness`在`[0,1]`。Base 1.0`alpha_mode`固定为`opaque`且两个alpha都必须1.0；不冻结cross-renderer blend sorting，也不支持alpha mask、texture或renderer-specific shader parameters。

Scene Compiler 的默认映射：

- Product material RGB -> `base_color.rgb`。
- 未指定 RGB -> 第 10.4 节固定的 neutral CAD color `[0.72, 0.75, 0.78]`。
- Alpha 固定为 1.0。
- Metallic/roughness始终使用`0.0`/`0.55` deterministic defaults，因为当前Product Material没有explicit PBR fields；不根据material name猜测。
- Appearance `source` 保留 root-scoped physical material provenance。

后续可以增加明确的 product-to-appearance assignment API，但不能根据 `steel`、`aluminum` 等名称启发式猜测 PBR 参数并宣称为 canonical material fact。

Scene 1.0 的 node-level required-nullable field 统一命名为 `appearance_override_id`，用于实例显示 override。没有 override 时值为 `null`；非 null 时必须引用 manifest `appearances` 中存在的 record，只影响 presentation，不修改 `Part.material`。

## 12. Camera、Light 与 Presentation

### 12.1 Camera

Scene 可以保存作者发布的 named camera：

```json
{
  "camera_id": "camera/gearbox-published-view/isometric",
  "name": "Isometric",
  "projection": "perspective",
  "parent_node_id": null,
  "transform": {
    "origin": [120.0, -160.0, 110.0],
    "x_axis": [1.0, 0.0, 0.0],
    "y_axis": [0.0, 0.0, 1.0],
    "z_axis": [0.0, -1.0, 0.0]
  },
  "vertical_fov_degrees": 35.0,
  "near": 0.1,
  "far": 100000.0
}
```

Camera 自己保存 parent-relative rigid transform，`parent_node_id` 可以引用 scene occurrence，也可以为 `null`。Camera local `-Z` 是 forward，local `+Y` 是 up。Perspective camera 必须满足 `0 < vertical_fov_degrees < 180`、`near > 0`、`far > near`；Orthographic camera 使用正数 `vertical_span`，不能同时保存 FOV。Near、far 和 vertical span 使用 scene length unit。

如果 scene 没有 camera，Viewer 应根据 world bounds 执行 deterministic fit-to-view，而不是要求 exporter 写入一个假的 camera。

### 12.2 Light（Base 1.0 Reserved）

第一阶段 Viewer 使用实现定义的 studio lighting。Base Scene 1.0 要求 `lights=[]`，不冻结半完整的 light record。Author-controlled directional、point 和 environment light 以后通过 required extension 引入，extension 必须定义 transform、color space、intensity unit 和 deterministic ordering。

### 12.3 Background 与 Environment

默认 background/theme 属于 Viewer preference。只有作者明确发布 presentation 时才进入 scene。Viewer preference 不应因为加载另一个 model 而永久被 scene 覆盖。

### 12.4 ScenePresentationSpec

Presentation spec 是独立、版本化、JCS-serializable 的 authoring input。最小结构：

```json
{
  "schema_version": "1.0",
  "presentation_id": "gearbox-published-view",
  "source_scene_id": "gearbox-demo",
  "appearances": [
    {
      "name": "Highlight",
      "base_color": [1.0, 0.55, 0.05, 1.0],
      "metallic": 0.0,
      "roughness": 0.45,
      "alpha_mode": "opaque",
      "double_sided": false,
      "edge_color": [0.12, 0.06, 0.0, 1.0]
    }
  ],
  "node_overrides": [
    {
      "node_id": "instance/main/stage1/input-shaft",
      "visible": true,
      "appearance_name": "Highlight"
    }
  ],
  "cameras": []
}
```

Base`ScenePresentationSpec`只允许上述`schema_version`、`presentation_id`、`source_scene_id`、`appearances`、`node_overrides`和`cameras`字段；未知字段fail closed。`source_scene_id`必须exact等于compile target`scene_id`。Appearance names、camera names和node override`node_id`分别唯一。Compiler将每个authoring appearance与presentation source scope组合、生成evaluated Appearance及content-derived`appearance_id`，再把`appearance_name`resolve为scene node的`appearance_override_id`。Appearance override只能target renderable Part/Shape，Assembly target失败；visibility override可target任意node。Presentation references stable scene node IDs或`SelectionRef`，不直接引用triangle ordinal、OCC hash或workspace-only GPU pick ID。Compiler必须验证所有refs；找不到target直接失败。Migration tool可在canonical compilation之外报告问题，但compiler不产生warning scene，也不从上一个evaluated manifest猜测presentation intent。

Presentation appearance exact fields是`name`、`base_color`、`metallic`、`roughness`、`alpha_mode`、`double_sided`、`edge_color`，其中`alpha_mode="opaque"`且alpha=1。Presentation camera exact fields是`name`、`projection`、`parent_node_id`、`transform`、`near`、`far`以及projection-specific`vertical_fov_degrees`或`vertical_span`；它不包含`camera_id`。Compiler按第16.1节统一segment encoder将authoring name编码为`camera/<presentation_id>/<encoded-camera-name>`。Node override只允许`node_id`、optional`visible`和optional`appearance_name`，且后二者至少存在一项。所有nested records使用第7.2节unknown-field/null policy。Base 1.0只拥有named views，不定义active/default camera；workspace选择的当前camera不进入canonical scene。

## 13. Annotation、Dimension 与 Measurement

### 13.1 Annotation（Base 1.0 Reserved）

Scene annotation 是 presentation object，不是 CAD feature，潜在类型包括：

- Label。
- Callout。
- Section marker。
- Read-only dimension display。
- Warning/diagnostic marker。

但 Base Scene 1.0 要求 `annotations=[]`，`ScenePresentationSpec` base schema 也不接受 annotations。Annotation extension 必须定义 annotation ID、kind-specific payload、units、style、`SelectionRef` target union、source kind 和 deterministic ordering。Source kind 至少包括：

- `authored`
- `derived`
- `diagnostic`

### 13.2 Measurement 精度边界

Mesh-only Viewer 可以可靠提供：

- Triangle/vertex coordinate。
- Approximate point distance。
- Approximate angle。
- Mesh bounds。
- Section visualization。

Mesh-only Viewer 不能宣称提供任意 analytic BRep exact measurement。圆柱半径、曲面距离、精确 edge length 等能力需要以下至少一项：

1. 后端 CAD query/measurement service。
2. Optional BRep asset 和 browser CAD kernel。
3. Exporter 预计算的 typed exact properties。

任何提供 measurement 的 UI 都必须区分 `exact`、`derived` 和 `mesh_approximate`，不能把 mesh 测量显示为无误差的 CAD measurement。Measurement 在 Phase D，不是 Phase C Viewer MVP 的退出条件。

## 14. Assembly 与 Kinematics

### 14.1 MVP

MVP Scene 保存 solved/evaluated component transforms。Viewer 不重新运行当前 Python assembly solver。

这支持：

- Product tree。
- Part isolate/hide/show。
- Repeated instance selection。
- Exploded view。
- Current pose display。

### 14.2 后续 Kinematic Projection

后续 scene capability 可以从 assembly constraints 派生只读 kinematic data：

- Revolute joint axis、current angle、limits。
- Prismatic axis、current distance、limits。
- Coupling relation。
- Connector frames。

该 projection 用于 Viewer motion preview，不成为 assembly constraint canonical owner。复杂闭环或 solver-dependent motion仍应由后端求解并发送 transform updates。

### 14.3 Evaluated Connector Snapshot

Scene Base 1.0 的 `connectors` 保存 Product `Part`/`Assembly` connectors 的 evaluated、只读 projection：

```json
{
  "connector_snapshot_id": "connector/main/part/input-shaft/mount-face",
  "owner_definition_id": "definition/main/part/input-shaft",
  "connector_id": "mount-face",
  "name": "Mount Face",
  "anchor_kind": "geometry",
  "local_transform": {
    "origin": [0.0, 0.0, 50.0],
    "x_axis": [1.0, 0.0, 0.0],
    "y_axis": [0.0, 1.0, 0.0],
    "z_axis": [0.0, 0.0, 1.0]
  },
  "target": {
    "entity_asset_id": "sha256:...",
    "entity_id": "entity/face/0"
  },
  "source": {
    "kind": "model_operation",
    "graph_id": "gearbox",
    "node_id": "node_connector",
    "output_slot": 0
  },
  "sdk_metadata": {}
}
```

`local_transform` 是 owner definition-local evaluated connector frame，不是 occurrence/world transform。Viewer 在某个 component occurrence 中显示 connector 时组合 `node_world_transform * local_transform`。一个 definition connector 自动出现在其所有 occurrences；Editor 必须明确提示“编辑 definition 将影响 N 个 instances”，不能误导为只修改当前 occurrence。

字段条件：

- `anchor_kind=geometry`：owner definition必须是`part`；`target` required，其exact fields是`entity_asset_id`、`entity_id`；asset必须由owner definition引用，entity kind必须是`face`、`edge`或`vertex`；`forwarded_from`必须省略。Base 1.0只接受能证明target属于owner Part body的geometry connector。Foreign-body target、standalone Shape connector或Assembly geometry connector compilation失败，不把不明坐标系的frame标记为owner-local。
- `anchor_kind=placement`：owner definition必须是`part`或`assembly`；`target`和`forwarded_from`都必须省略。
- `anchor_kind=forwarded`：owner definition必须是`assembly`；`forwarded_from` required，`target`必须省略。`forwarded_from` exact fields是`source_component_id`、`source_definition_id`、`source_connector_id`、`source_connector_snapshot_id`和nullable`offset`；`offset`使用canonical rigid transform。前两个Product-local IDs保留authoring audit，后两个scene IDs使package validator能验证target connector。
- `source` 为 nullable；非 null 时 exact variant `kind=model_operation` 包含 `kind`、`graph_id`、`node_id`、`output_slot`，`kind=manual` 只包含 `kind`、`source_id`。
- `sdk_metadata`在Base 1.0固定为`{}`。当前Connector `_metadata`既未进入`Connector.to_dict()`也未被model replay保存，因此compiler不得投影它；future connector metadata需要recorded connector operation和profile/schema revision。

Compiler 必须确认 geometry connector 的 resolved target 与 entity source provenance 一致，并确认 `local_transform` 按 SDK 现有规则求值：face origin/normal、edge midpoint/direction、vertex point/identity axes，再应用 `flip` 已产生的方向。Scene 不复制 `flip` authoring intent；该 intent 保留在 model connector operation 中。

Existing Product connector不是可以静默省略的optional snapshot。若geometry selector无法unique resolve、target不属于owner、`sdk_connector_frame=null`（例如current SDK closed edge）或placement/forwarded frame求值失败，整个compilation以stable`connector_frame_undefined`或更specific rule失败。`SceneConnector.local_transform`保持required non-null。Phase A/Compiler tests必须包含一个serialized/replayed closed-edge connector并证明它明确失败；未来profile定义closed-edge tangent frame后才可导出该connector。

Forwarded snapshot必须满足以下可独立验证的resolution contract：

1. `source_connector_snapshot_id`必须引用恰好一个connector，其`owner_definition_id=source_definition_id`且`connector_id=source_connector_id`。
2. 对owner assembly definition的每个occurrence node，都必须存在恰好一个direct child node，child的`source.component_path`等于owner occurrence path追加`source_component_id`，并引用`source_definition_id`。所有这些child nodes的local transform必须相同；否则definition equivalence已经被破坏，package无效。
3. Forwarded`local_transform`必须等于`source child local transform * source connector local_transform * offset`；`offset=null`按identity处理。Composition按第7.4节row-major/column-vector rigid-transform顺序，在binary64中以profile固定multiply/add order且禁止FMA；origin逐component用`epsilon_mm`比较，axis逐componentabsolute error`<=1e-12`。
4. 以`connector_snapshot_id -> source_connector_snapshot_id`建立directed graph，必须无self-edge、无cycle且最大chain depth不超过resource profile。Source connector可以是geometry、placement或另一个valid forwarded snapshot。
5. `source_component_id`必须是owner assembly direct component，而不是descendant path或任意matching occurrence。缺失、多个source child、definition mismatch、dangling snapshot或frame mismatch都使package失败。

Model-backed scene中，connector `source`必须是`model_operation`并能在exact graph中找到valid output slot；manual scene中必须是`manual`。Imported scene可以使用`source=null`，但不能伪装为model operation。每个owner definition内`connector_id`唯一；`connector_snapshot_id`必须等于第16.1节owner kind/semantic ID/connector ID推导的structural ID，而不是任意label。

`model_operation`的canonical producer不是独立Connector creation node，而是将该connector首次引入其owner Product definition的unique graph output：attached Part使用`make_add_connector_rpart`，attached Assembly使用`make_add_connector_rassembly`，forwarded connector使用`make_forward_connector_rassembly`，三者`output_slot`在Model Schema 2.0均固定为0。Compiler必须证明producer input owner尚无该`connector_id`、producer output owner恰有equal connector record，且从producer到selected owner definition output的replay lineage没有删除或替换该record；缺失或多个candidate以`connector_source_unproven`失败。Geometry/placement connector creation operation只提供anchor intent，不写入`SceneConnector.source`。Manual scene的connector `source.source_id`必须exact等于top-level manual `SceneSource.source_id`；connector自身identity由`connector_snapshot_id`提供，不另生成path、UUID或sequence-derived source ID。

### 14.4 Connector Binding Authoring

Viewer/Editor 通过独立 `ConnectorBindingSpec` 请求创建 connector。Base command 使用 JCS，exact top-level fields 为：

```json
{
  "schema_version": "1.0",
  "binding_id": "bind-input-shaft-mount",
  "source_model": {
    "graph_id": "gearbox",
    "model_schema_version": "2.0",
    "artifact_hash": "sha256:..."
  },
  "source_scene": {
    "scene_id": "gearbox-demo",
    "revision": "sha256:..."
  },
  "owner_definition_id": "definition/main/part/input-shaft",
  "selected_occurrence_node_id": "instance/main/stage1/input-shaft",
  "connector_id": "mount-face",
  "name": "Mount Face",
  "target": {
    "kind": "topology_entity",
    "entity_asset_id": "sha256:...",
    "entity_id": "entity/face/0",
    "expected_source": {
      "kind": "model_output",
      "graph_id": "gearbox",
      "node_id": "node_...",
      "output_slot": 0
    },
    "flip": false
  }
}
```

所有 top-level fields required；只有 `name` nullable。`source_model`、`source_scene` 和 topology `expected_source` 不允许额外字段。`binding_id` 使用 caller-authored Scene ID grammar。`connector_id` 使用现有 Product identifier grammar `[A-Za-z][A-Za-z0-9_.:-]*`，嵌入 structural ID 时按第 16.1 节 percent encode。Base `target.kind=topology_entity` 只接受 face、edge、vertex entities，因为当前 SDK connector operations只对这些 topology kinds 定义 frame derivation。

后续 `feature_output` target variant 可以引用 `graph_id`、`node_id`、`output_slot` 和一个版本化 frame derivation rule，例如 operation context frame；它要求新增 canonical model operation，不能在 Viewer 中把一次 evaluated transform 偷换成 durable feature binding。Solid/feature node 可用于 DAG 定位，但在该 operation 落地前不能保存为 geometry connector。

Backend apply 流程必须原子执行：

1. 从受控registry取得或随request接收完整source `CompiledScenePackage`，执行full package validation，并验证当前model exact-byte hash、graph ID、scene ID和revision全部匹配command preconditions。
2. 验证 selected occurrence 引用 owner definition，entity asset 和 entity record 仍存在。
3. 比较 entity `source` 与 `expected_source` 的全部字段，拒绝 stale 或 unbound/imported target。
4. Replay exact model，并使用source scene中冻结的roots、compile options和toolchain profile重新编译pre-mutation scene；其revision和全部referenced asset hashes必须与command source scene相等，否则返回conflict。
5. 从该次trusted compilation产生的ephemeral resolution index中，用 `(owner_definition_id, entity_asset_id, entity_id)` 取得唯一 live face/edge/vertex。Index不是artifact，也不能通过geometry-nearest search替代；zero或multiple matches都失败。
6. 从resolved live entity建立当前SDK canonical `GeometryRef`，调用对应face/edge/vertex connector operation，并把connector加到owner Part definition；重复connector ID失败。
7. 导出新的model artifact，再以同一stable `scene_id`、root descriptors和compile options重编译scene。
8. 返回新model hash、新scene revision、connector snapshot ID和`SceneValidationReport`；report不进入新scene revision。

`expected_source` 是 provenance/staleness precondition，不是单独的subshape selector。Target entity还必须有`connector_binding_status="supported"`。`model_topology`可以提供更强artifact evidence，但Base 1.0不要求它；`model_output` target依靠exact source model + exact source scene + deterministic recompilation index完成revision-local resolution。Backend不得直接用`topo_id`、OCP hash、runtime traversal ordinal或non-unique selector score猜目标。若当前toolchain无法重现source revision，command必须失效并要求重新选择。

Recompilation recipe来自validated source manifest：root occurrence及其definition source恢复ordered `SceneRoot` descriptors，其中`root_id`来自root occurrence source、`value`来自exact definition/model output、`transform`来自root occurrence的exact transform；top-level `compile_options`提供resolved options，`source`提供exact model precondition。标记为self-contained model package时，source model和所有manifest-declared project-relative Python sources必须已经在package中；registry fallback只适用于明确发布为non-self-contained的generic package或optional presentation。若`presentation_source`存在，backend还必须取得hash匹配的exact presentation JCS bytes。缺少任一root output、source model、presentation artifact或matching complete generator/toolchain时，backend不能advertise `cad_verified`，apply返回unsupported/conflict而不是省略输入后尝试“近似重编译”。Binding command本身不复制这些可能很大的artifacts。

普通静态 Viewer 可以只导出 `.json` command；有 backend 的 Editor 可以直接提交。无论 transport 如何，成功前不得本地篡改 canonical scene/model；可以用 workspace-only optimistic gizmo 显示 pending connector。Revision/hash conflict 必须提示用户 reload/reselect，不能自动将 command 迁移到 geometry-nearest entity。

当前 SDK 能对一个 live `Part` value执行 geometry connector + `add_connector_rpart`，但 public serializer不能从 standalone uploaded `model.json`恢复一个可继续append operations、替换captured results并原子rollback的 editable `GraphSession`。它也不能自动把 nested immutable Part的新版本重接到所有parent assemblies。因此 Base binding command可以先稳定生成/验证，但hosted apply在新增 `import_model_session`/model transformation transaction前一律unsupported。该transaction必须adopt并strictly validate imported graph、append canonical operations、替换result IDs、重建affected Product operations、export新model，并在任一步失败时保持原artifact不变。

同进程保留原始 live `ModelResult.session` 的实验性apply也必须使用显式transaction API后才能advertise capability，不能直接mutate session并假装atomic。Nested Part apply还必须确定性重建affected parents并保持unrelated graph intent。Viewer根据backend capability response禁用unsupported apply，不能把scene occurrence局部添加connector当作成功。

Assembly connector authoring 使用 placement connector 或 forwarded connector 的独立 command variant，不从 assembly descendant face 隐式创建 geometry connector；该 variant 不属于 Base `topology_entity` binding。

## 15. Scene Package

推荐发布格式扩展名为 `.scene.zip`，本质是 ZIP package：

```text
gearbox.scene.zip
├── scene.json
├── geometry/
│   ├── sha256-abc.glb
│   ├── sha256-def.glb
│   └── sha256-ghi.glb
├── edges/
│   ├── sha256-jkl.glb
│   └── sha256-mno.glb
├── entities/
│   ├── sha256-abc.json
│   ├── sha256-def.json
│   └── sha256-ghi.json
├── model/
│   └── model.json              # self-contained model package required
├── sources/
│   └── models/
│       └── gearbox.py          # preserved project-relative path
└── presentation/
    └── presentation.json       # optional
```

开发模式同时支持 unpacked directory，便于 diff、调试和静态 HTTP hosting。Packed 与 unpacked 形式必须拥有相同 `scene.json` 和 asset bytes。

### 15.1 Render-self-contained 与 Self-contained Model Package

Viewer 必须能够只依赖 `scene.json` 和 referenced geometry/edge/entity assets 完成显示与五层 selection；这是render-self-contained scene。Generic low-level package可以不嵌入model。Self-contained model package还必须包含exact `model/model.json`和`source_files`声明的Python files，用于：

- Download original model。
- Backend replay。
- Features history/source panel。
- Exact CAD service。

缺少 embedded model 或 presentation source 不得阻止普通 Viewer 加载render scene，但Features/source capability必须disabled。Compiler-produced `@model(export_dir=...)`和`ModelResult.export_artifacts()` package属于self-contained model package，总是嵌入model并输出`source_files`，后者没有可解析source时可以是空array。若embedded artifacts存在，loader必须按manifest中的URI、byte length和artifact hash验证，不得因为文件位于约定目录就默认信任。

### 15.2 URI 规则

Scene 1.0 URI是opaque ASCII ZIP member name，不是RFC URL：不执行percent decode、query/fragment split、Unicode normalize、base URI resolution或filesystem path semantics。Grammar固定为`[A-Za-z0-9][A-Za-z0-9._/-]{0,1023}`，使用`/`separator；每个segment必须non-empty且不能是`.`或`..`。`%`、`?`、`#`、backslash、colon、NUL、leading/trailing slash、absolute path和drive prefix全部拒绝。HTTP、`file://`和external transport不属于Base 1.0。

Loader必须在读取任何payload前拒绝duplicate/case-insensitive-colliding member names、encrypted/non-regular entries和unsupported compression。ASCII restriction使Unicode database/version不参与package identity。Package member set必须exact等于`scene.json`加manifest中所有geometry/edge/entity/model/source-file/presentation URI的set；每个non-scene member至少被一个record引用，相同URI的所有records必须声明相同hash/length/media role。`source_files[].path`是不含`sources/`的project-relative path，`uri`必须是exact `sources/<path>` transformation。其他member一律拒绝。

Packed loader优先从archive stream读取，不extract到filesystem。必须extract时，每个目标的resolved realpath必须位于新建package root内，并以no-follow方式创建；unpacked directory loader同样拒绝symlink并检查每个resolved path containment。Unpacked loader必须先以no-follow enumeration/stat收集所有regular-file ASCII member names和uint64 sizes，在读取任何payload前验证name/collision/member-count、per-file limits、checked total uncompressed bytes、exact canonical stored size及non-ZIP64 representability；之后只先读取budgeted `scene.json`来验证exact member set，再读取referenced immutable blobs。Enumeration与open之间任何type/size/file-identity变化都以TOCTOU error失败。Archive不得有leading prefix或EOCD后的trailing bytes。Central/local header的name、size、CRC-32、flags和method必须一致；data descriptor、ZIP64、multi-disk、archive/member comment和extra field全部拒绝。Import只允许creator OS Unix、version needed/made-by 2.0、flags exact`0x0800`、method stored(0)或deflate(8)、disk fields 0、internal attributes 0，且external attributes high 16 bits必须是Unix regular file mode`0100644`。

Canonical`.scene.zip` exporter无directory entries，members按ASCII path bytes unsigned lexicographic order，method stored。每个local header固定：signature`0x04034b50`、version needed`20`、flags`0x0800`、method`0`、DOS time`0`、DOS date`0x0021`、actual CRC-32、equal compressed/uncompressed uint32 sizes、actual filename length、extra length`0`。每个central header固定：signature`0x02014b50`、version made by`0x0314`、version needed/flags/method/time/date/CRC/sizes与local一致、extra/comment/disk/internal attributes均`0`、external attributes`0x81A40000`、actual local offset。EOCD固定single-disk zero fields、matching uint16 entry counts、actual central size/offset和zero comment。Archive总长度和all offsets用checked arithmetic且不得需要ZIP64。Importer可以接受上述allowlist内deflate package，但必须在接受前按payload lengths和member name bytes计算canonical stored envelope size并满足第22.2节budget；重新export时只canonicalize envelope，payload bytes不变，不保留原compression bytes。Phase A exact ZIP vector是这些fields的normative byte oracle。

所有JSON在object construction前检测duplicate member names；发现任何层级duplicate key立即拒绝，不能依赖parser的first/last-wins行为。JSON输入必须是strict UTF-8，不接受BOM、replacement decoding、comments或trailing tokens。`scene.json`、entity sidecars和embedded presentation必须逐byte等于parsed value的RFC 8785 JCS encoding；noncanonical whitespace、number或member order直接拒绝。Embedded model/imported source bytes保持其source-defined raw encoding。Python source blobs是strict UTF-8 inert text，不是JCS documents；package validator按immutable bytes验证length/hash并将operation source spans与文本cross-check。Hash、byte length和validation必须消费同一份immutable bytes；validator验证的member/JSON/GLB/source bytes就是后续renderer或inspector读取的bytes，禁止按路径二次打开造成TOCTOU/parser confusion。

## 16. Identity、Revision 与 Content Hash

必须区分四种 identity：

| Identity | 用途 | 生成策略 |
| --- | --- | --- |
| `scene_id` | 一个长期 scene 的逻辑身份 | 调用方必须显式提供稳定 ID |
| `revision` | Scene manifest 的不可变版本 | Canonical manifest content hash |
| `node_id` | Revision 间尽量稳定的 occurrence identity | Product component path 优先 |
| content asset ID | Geometry、edge 或 entity snapshot bytes identity | SHA-256 content hash |

### 16.1 ID Grammar 与 Segment Encoding

Scene 1.0 的 caller-authored `scene_id`、`root_id` 和 `presentation_id` 使用：

```text
[A-Za-z][A-Za-z0-9_.-]{0,127}
```

禁止 `/`、`:`、`%` 和 whitespace。Content IDs 使用 exact lowercase form：

```text
sha256:[0-9a-f]{64}
```

Product IDs 当前允许 `:`，因此不能直接拼接到 structural ID。每个 product/component/graph/node semantic segment 必须先按 UTF-8 编码，再使用 RFC 3986 percent encoding；只保留 ASCII unreserved `A-Z a-z 0-9 - . _ ~`，其他 bytes 包括 `/` 都必须编码，percent hex 必须 uppercase。Decoder 必须拒绝对 unreserved byte 的多余编码、lowercase percent hex、invalid UTF-8 和 decode/re-encode 不一致。

Structural IDs 使用固定 literal segments 和 `/` 分隔：

```text
definition/<root_id>/<kind>/<encoded-semantic-id>
instance/<root_id>/<encoded-component-id>/...
definition/<root_id>/shape/model/<encoded-graph-id>/<encoded-node-id>/<output-slot>
definition/<root_id>/shape/imported/<encoded-source-element-id>
definition/<root_id>/shape/manual/<encoded-source-id>
appearance/<scope>/<sha256-hex>
connector/<root_id>/<owner-kind>/<encoded-owner-id>/<encoded-connector-id>
```

Base 1.0 的 `<scope>` 固定 literal `evaluated`，因此所有 evaluated appearance ID恰为 `appearance/evaluated/<sha256-hex>`；source/presentation scope已包含在被hash record中，不再编码第二种ID grammar。

由于 data segments 不允许 raw slash，tuple-to-string mapping 无歧义。Validator 必须在构造 registry 前拒绝 duplicate canonical IDs；不能先由 mapping 覆盖再检查。

### 16.2 Product-backed IDs

Product hierarchy 中：

- Definition ID 使用 root namespace 和 typed semantic ID，例如 `definition/<root_id>/part/<encoded-part-id>`、`definition/<root_id>/assembly/<encoded-assembly-id>`。
- Scene node ID 来自 root identity 和完整 component path。
- 同一个 root namespace 内，同一 semantic type/ID 必须表示同一 definition；compiler 发现不同 producer/content 时失败。
- 不同 roots 可以使用相同 product ID 并生成不同 definitions；geometry bytes 仍通过 content hash 跨 definitions 去重。
- 同一 root 中 repeated Part/Assembly 复用同一 definition。

现有 Product API 没有 scene-wide global ID contract，因此 Scene 1.0 不宣称裸 `part_id` 在多 root scene 中全局唯一。`SceneRoot.root_id` 是 identity contract 的必要部分。

同一 root 内的 definition equivalence 使用第 10.4 节 exact normalized Product records，不能仅比较显示名称或 mesh bytes，因为不同 product definitions 可以具有相同 geometry。

每个 root 自身也有 root occurrence node `instance/<root_id>`；descendant node 是 `instance/<root_id>/<encoded-component-id>/...`。因此两个 roots 包含相同 assembly/component path 时仍拥有不同的全局 node IDs。

### 16.3 Shape-backed IDs

Standalone graph shape 没有 product ID 时，definition identity 使用：

```text
definition/<root_id>/shape/model/<encoded-graph-id>/<encoded-node-id>/<output-slot>
```

Root occurrence 仍统一使用 `instance/<root_id>` 并引用上述 definition；不再使用第二套 `shape/...` node identity。Definition identity 只保证在同一个 exported model artifact 内稳定。由于当前 operation node IDs 默认是随机短 ID，独立重建的等价 model 不保证产生相同 definition ID。发生这种情况时，patch 系统应发送 full replacement 或要求作者提供稳定 semantic ID，不能用 geometry proximity 猜测对象 identity。Imported/manual shape 使用其对应 source variant；调用方没有 stable source identity 时 compilation 失败。

### 16.4 Canonical JSON

Scene manifest、entity snapshot sidecar、optional presentation spec 和 connector binding spec 使用 RFC 8785 JCS。为了得到稳定 revision，必须满足：

- UTF-8 和 JCS string/number/object-key encoding，包括 `-0`、Unicode 和 IEEE-754 finite number 的 JCS 处理。
- 禁止 NaN 和 infinity。
- Hash input 完全省略顶层 `revision` 字段，不使用空字符串或 placeholder。
- Canonical package中的JSON member必须就是compact JCS bytes；pretty rendering只允许UI显示，不能作为valid package member。

JCS保留array order，因此compiler在JCS前必须规范化所有set-like arrays。Validator不silently normalize wire input；任何array不是canonical order就拒绝，再对unchanged parsed value重算revision。JSON object member names严格使用RFC 8785要求的UTF-16 code-unit ordering，由JCS encoder负责。除此之外，本文显式要求排序的schema arrays、IDs、logical names和ASCII package paths固定使用unsigned UTF-8 byte lexicographic order；不使用Python code-point或JavaScript默认comparator：

- `extensions_used=[]`、`extensions_required=[]`和`extensions={}`，non-empty直接拒绝。
- `definitions` 按 `definition_id` sort，`nodes` 按 `node_id` sort。
- `geometry_assets` 和 `edge_assets` 按 `asset_id` sort，`entity_assets` 按 `entity_asset_id` sort。
- `appearances` 按 `appearance_id` sort，`connectors` 按 `connector_snapshot_id` sort，`cameras` 按 `camera_id` sort。
- Base 1.0的`lights`、`annotations`和`diagnostics`必须为空。
- semantic binding IDs 和 evaluated tags lexicographic sort。

`component_path`、matrix/vector、face/edge range和其他语义上有顺序的arrays保留schema-defined order。Entity payload中的`entities`、`face_groups`和`edge_groups`也必须already满足第10.2/10.4节order。Scene validator只验证order并按原value JCS重算revision，不将多个wire manifests折叠到同一revision。

## 17. Scene Compiler

### 17.1 编译输入

推荐 API：

```python
package = scad.compile_scene(
    scene_id="gearbox-demo",
    roots=(scad.SceneRoot(root_id="main", value=assembly),),
    source=result,
    presentation=None,
    options=scad.SceneCompileOptions(
        linear_tolerance=0.35,
        angular_tolerance=0.22,
    ),
)
```

`scene_id` 是 required keyword-only input；compiler 不生成 UUID、timestamp 或 path-derived fallback。`source` 可以是 `ModelResult` 或显式 `SceneSource` descriptor。它不选择 `roots`，但不是可随意填写的 label：`source.kind=model` 时 compiler 必须拥有 source `GraphSession`/artifact ownership evidence，并验证每个 graph-backed root、Part body、definition source、entity source、connector source和 semantic binding都属于同一 exact source graph/model artifact。调用方只提供 hash/graph ID而没有 ownership evidence时，不允许生成 `kind=model` scene；应使用 imported/manual source或先通过 trusted replay service建立 evidence。`presentation` 可以是 `ScenePresentationSpec`；省略时只生成 deterministic default appearance/visibility，不保存作者自定义视图。Entity snapshots 和 CAD edge assets 是 Base Scene 1.0 renderable definition 的 mandatory output，不提供 disable option。

`SceneCompileOptions`在Base 1.0中是closed immutable record，只含`linear_tolerance`、`angular_tolerance`、`embed_source`和`embed_presentation`。两种tolerance省略时分别固定为`0.35` mm和`0.22` radians；embedding booleans都默认false。显式tolerance必须finite，`0 < linear_tolerance <= 1000000.0`且`0 < angular_tolerance <= 3.141592653589793`。同一linear tolerance同时用于triangle deflection和CAD edge discretization；不另设hidden edge default。Compiler必须把四个resolved values写入manifest并纳入cache/revision input。Meshing parallelism、thread count、OCP environment或process cache不得改变canonical output；当前profile无法满足时必须按profile单线程规范化或失败。

`roots`必须是non-empty tuple，`root_id`唯一；每个root必须产生一个root occurrence和definition。RenderablePart/Shape必须包含至少一个valid solid、face、edge和vertex，并生成non-empty triangle/line assets；empty shape、wire、shell、vertex-only、edge-only、face-only、zero-solid Compound和fully-collapsed tessellation在Base 1.0中失败。纯Assembly可以没有自身geometry，但其recursive descendants必须至少包含一个renderable definition；完全空scene只能由低层schema fixture构造，不能由`compile_scene()`产生。

Ownership validation至少执行 `GraphSession.validate_graph_ownership()` 等价检查，并验证所有 `model_output`/`model_topology` 的 `(node_id, output_slot)` 在exact model graph中存在、slot小于`output_count`；只有`model_topology`要求其topology tuple能在artifact records中找到。所有semantic binding IDs必须存在且target/source一致。任何imported/unbound entity不能伪装为model provenance。Package validator对embedded model重复执行纯结构cross-check；trusted compiler负责证明runtime geometry确由这些roots求值，并为connector apply产生不序列化的entity-to-live-shape index。

`compile_scene()` 返回 `CompiledScenePackage`，而不是裸 `SceneSnapshot`。Package 是 immutable aggregate，至少包含：

- `manifest: SceneSnapshot`
- `blobs: Mapping[str, bytes]`，key 是 manifest 中 package-relative URI
- Generic package中按options选择的embedded source/presentation blobs
- Compiler-produced self-contained model package中的mandatory `model/model.json`和manifest-declared `sources/**/*.py`

这样 asset bytes 的所有权和生命周期是显式的，compiler 不依赖临时目录、隐藏 mutable state 或进程内 cache 才能完成 export。`CompiledScenePackage`不保存输入ZIP envelope或compressed sizes。当前public slice提供`preflight_zip_bytes()`和package validator组合加载archive bytes；后续`import_scene()`可以在此边界上返回同一package type。Accepted package可以payload-byte-preserving地重新export为canonical stored envelope，但不会保留原compression bytes或header布局。

不建议在 `ModelResult` 上自动增加 eager `scene_json` 属性。Scene compilation 包含昂贵 tessellation 和 binary asset generation，不能成为每次`@model`调用的无条件成本。当前支持两个显式opt-in入口：decorator的`export_dir`和调用后的`ModelResult.export_artifacts(output_dir=...)`；省略二者时保持in-memory-only行为。

### 17.2 编译过程

Scene Compiler 按以下顺序工作：

1. 验证root descriptors、root value类型、root IDs和graph ownership；model source先clean replay exact artifact并验证projected runtime metadata equality。
2. 解析replayed model或manual root为standalone shape或product definition/instance tree；imported root只解析为standalone shape。
3. 建立全局definition registry，包括flattened Compound owner metadata exception。
4. 递归遍历 assembly，组合并验证 component path，但只保存 local placement。
5. 对每个 unique geometry definition 生成或复用 RenderMesh。
6. 生成 normals、CAD edge polylines 和 local bounds。
7. 建立 solid/face/edge/vertex entity records、face/edge picking ranges 和 graph/topology provenance。
8. 将 Product Material 映射为 Appearance，并求值 definition connectors。
9. 当嵌入model时，从live graph nodes收集所有`path_kind=project_relative` source；验证file仍位于其`pyproject.toml` project root、path仍一致、member path archive-safe、文件存在且是strict UTF-8 `.py`，拒绝case-fold collisions，并按path排序/deduplicate。
10. 写出 deterministic triangle GLB、edge GLB、entity snapshot sidecar、exact model bytes和`sources/<project-relative-path>` bytes。
11. 计算所有 blob hashes，建立不含 `revision` 的 draft manifest。
12. 执行 structural draft validation。
13. 使用 normalized JCS draft manifest 计算 scene revision，并构造 final manifest。
14. 构造 `CompiledScenePackage`。
15. 执行包含 URI、byte length、blob hash、GLB profile、entity adjacency/range、embedded model graph references、source span/callsite和revision 的 full package validation。

### 17.3 Compound 策略

`Compound` 没有 product hierarchy 时，第一阶段将其视为一个 shape definition 和一个 render object。不能根据 disconnected solids 的空间位置猜测 component identity。

后续可增加 explicit shape group input，但不自动把所有 compound children 提升为可持久化 product nodes。

### 17.4 Cache Key

Render mesh cache key 至少包括：

- Geometry source content/evaluation identity。
- Linear tolerance。
- Angular tolerance。
- Normal generation policy version。
- Edge tessellation policy version。
- Render asset schema version。
- OCP/kernel 和 tessellator build identity。
- 全部 meshing flags。
- Normal/edge generation implementation version。
- GLB writer/profile version。
- Numeric/float normalization profile。

Placement、visibility、camera 或 appearance-only changes 不得使 geometry asset cache 失效。

Deterministic asset hash的保证范围是：相同exact source artifact、相同geometry value、相同compile options、相同profile ID/profile bytes和相同registered `toolchain_hash`。只匹配profile ID但toolchain hash不同不能声称byte-for-byte reproducible。Scene revision还要求相同`scene_id`、resolved roots、presentation和完整exact `generator` record；任一display version、ABI/platform token、toolchain hash或profile变化都会按manifest内容产生新revision。跨OCP/tessellator/writer toolchain的byte-for-byte equality不是Scene 1.0保证；toolchain/profile变化必须cache miss并进入generator metadata。

## 18. Public API 草案

第一阶段推荐最小 API：

```python
package = scad.compile_scene(
    scene_id="model-preview",
    roots=(scad.SceneRoot(root_id="main", value=value),),
    source=model_result,
    presentation=presentation,
    options=options,
)

scad.validate_scene_manifest(scene=package.manifest)
scad.validate_scene_package(package=package)
scad.export_scene(package=package, path="model.scene.zip")

@scad.model(graph_id="model", export_dir="out")
def build_model():
    return build_part()

result = build_model()
assert result.artifact_paths["scene"].name == "model.scene.zip"
```

也可以不在decorator传`export_dir`，随后调用`result.export_artifacts(output_dir="out")`。这两个automatic publishing入口只在output directory中写一个Scene ZIP；model/session JSON和Python source位于ZIP内部，不自动生成旁置STEP、STL或FCStd。Archive import convenience尚未作为public API发布；当前读取边界是`preflight_zip_bytes()`、`parse_canonical_json()`和`validate_scene_package()`。

核心 public types：

- `SceneSnapshot`
- `CompiledScenePackage`
- `SceneRoot`
- `SceneSource`
- `ScenePresentationSpec`
- `SceneDefinition`
- `SceneNode`
- `SceneAppearance`
- `SceneGeometryAsset`
- `SceneEdgeAsset`
- `SceneEntityAsset`
- `SceneConnector`
- `ConnectorBindingSpec`
- `SceneCamera`
- `SceneCompileOptions`
- `SceneValidationReport`

`validate_scene_manifest()`只验证schema、IDs、hierarchy、transforms、references和revision。`validate_scene_package()`还验证所有referenced bytes、GLB allowlist/profile、entity adjacency/ranges、embedded model/source artifact和所有artifact-derived resource budgets；它不验证不存在于`CompiledScenePackage`中的input archive length、compressed sizes或compression ratios。Packed envelope或unpacked stat table由对应preflight先验证canonical stored archive size；`export_scene()`在写入前重复计算该size。Exporter还必须调用package validator；manifest-only validation不能声称package安全或完整。

不建议第一阶段提供大量 mutable `scene.add_node()` 风格 API。先以 immutable dataclass、compiler output 和 strict serializer 为主，避免形成第二套随意构造且无法验证的 scene graph。

## 19. Viewer Runtime 架构

### 19.1 独立 TypeScript/Three.js 工程

Viewer 位于仓库根目录 `viewer/`，拥有独立 `package.json`、TypeScript config、Vite build pipeline 和发布产物。它可以依赖发布后的schema fixtures/types，但不能import Python package internals，也不能要求SimpleCAD virtualenv、OCP或scene compiler才能启动。当前实现由`viewer/src/main.ts`直接管理DOM/UI和Three.js runtime，并未采用React。

当前主要目录：

```text
viewer/
├── package.json
├── src/
│   ├── main.ts               # package loader, UI state, Features, inspector
│   ├── style.css             # layout, source range and selection styling
│   └── components/
│       └── click-selection.ts
└── public/cases/             # optional static fixtures
```

TypeScript负责package/UI逻辑，Three.js `WebGLRenderer`负责imperative rendering。GLB只能从已经经过package member length/hash validation的in-memory bytes构造；package source不允许触发nested network/file resource resolution。Three.js是renderer adapter的实现细节，不改变Scene contract。

Camera pose、hover、GPU resources、pointer movement和renderer dirty flags保存在imperative runtime中；每帧camera update不重建UI。若未来迁移到React，仍应维持这一边界，但React store/hooks不是当前实现contract。

### 19.2 Package Loader 与未来配对

负责：

- 通过file picker或drag/drop加载一个local `.scene.zip`。
- 验证archive member policy、manifest references、byte length和SHA-256。
- 从package中发现并解析embedded `model/model.json`。
- 按`source.source_files`加载strict UTF-8 Python source。
- 验证通过后并行加载 GLB 和 entity assets。
- 建立 node/definition/asset registries。
- 根据 parent relation 计算 world transforms。

当前没有独立external model slot、unpacked-directory loader或完整pair-state UI。Validated package中存在embedded model时启用Features/source；否则保持scene-only模式，Preview、product tree和geometry selection仍可用。以下independent slots和配对状态是后续architecture，不是当前Viewer行为：

| 状态 | 条件 | UI/能力 |
| --- | --- | --- |
| `artifact_matched` | scene `source.kind=model`，且 exact model bytes SHA-256、graph ID、model schema version 全部相等 | Preview和DAG并列可用；在结构验证前不cross-link或author |
| `provenance_matched` | `artifact_matched` 且browser完成下述全部结构cross-check | 启用read-only DAG/entity双向定位和binding command draft/export；不代表CAD replay已验证 |
| `scene_only` | 只有 scene，且无 verified embedded model | Preview、tree、entity inspector 可用；DAG 和 authoring disabled |
| `model_only` | 只有 model | DAG/params 可用；viewport 显示 no evaluated scene，不执行 browser replay |
| `mismatched` | 两者都存在，且任一pairing field不同，或三个fields相等但任一required provenance cross-check失败 | 两侧仍可独立查看，显示stale/mismatch或invalid-provenance banner；禁止自动cross-link和authoring |
| `non_model_scene` | scene source 是 imported/manual | Preview 可用；model pairing 不适用 |

Hash 必须对用户选择的原始 `ArrayBuffer` 计算，不能 parse 后 reserialize 再计算。Embedded model也必须按manifest URI、byte length和hash验证后才能用于Features。未来若加入external model slot，external与embedded model不同时必须进入mismatch，不能静默优先任意一份。

Browser 对 operation JSON 只做 budgeted display/index validation，不 replay。DAG index 读取 `graph.graph_id`、`nodes[].node_id/op/params/param_exprs/inputs/output_count/display`、`edges`、`leaf_ids` 和 expression graph；必须检测 duplicate IDs、dangling inputs、cycles、`edges`/`inputs` disagreement 和超预算 payload。它不是 Python model importer 的安全替代品，connector apply backend 仍须执行 canonical model validation/replay。

Package validators已经验证每个model-backed definition/entity/connector `(graph_id,node_id,output_slot)`存在于embedded graph且slot有效，并验证operation source span/callsite。未来进入`provenance_matched`前，browser还应验证第14.3节完整connector producer contract、topology records、semantic bindings以及`edges`/`inputs`一致性。Browser静态检查不能声称已证明replayed input/output equality或geometry correspondence；后者仍由trusted compiler/backend验证。

未来的`provenance_matched`仍只是artifact/record consistency，不证明无OCP replay的browser重新建立了geometry correspondence。Connector command提交必须由backend返回`cad_verified` capability：backend重新验证exact model/scene preconditions、trusted compiler ownership evidence和target resolution后才执行mutation。

### 19.3 Renderer

负责：

- 按 geometry + appearance 对 repeated occurrences 做 instanced mesh rendering，并保留 `instanceId -> scene_node_id` map。
- PBR 或稳定 CAD studio shading。
- CAD edge overlay。
- Mesh ID pass、CAD line hit testing 和 runtime vertex point picking。
- Clipping planes。
- Grid、axes 和 background。
- Fit-to-view。

Renderer 对外只暴露typed commands/events，例如load package、set node visibility、set selection intent、fit bounds和resolved raw hit。DOM event handlers不应绕过renderer state随意mutate unrelated Three.js objects。Material创建从`SceneAppearance`确定性映射，definition appearance和node override按manifest precedence解析；material-aware preview不从mesh name猜测颜色。

### 19.4 Product Tree 与 Features

Tree 直接使用 scene node hierarchy，不解析 operation graph。Tree node 与 viewport occurrence 共享 `scene_node_id`。

当前Features tree读取embedded model：从`leaf_ids`开始递归跟随`inputs`，每个graph node只显示一次，再补上未从leaf访问的nodes；它显示operation dependency而不伪装成product hierarchy。选择feature时清除occurrence selection并显示：

- `op`、category、`node_id`、input node IDs、output count、tags和result/leaf status。
- 完整 JSON-safe `params`，不只显示 summary。
- Display summary和`assignment_targets`。
- Source path/call range；project-relative mapping通过`source_files[path]`显示完整Python file，高亮`line..end_line`并滚动到首行。
- Source unresolved或member缺失时显示`call_text` fallback。

当前不实现viewport/entity到feature的双向定位，也不在选择feature时高亮所有对应geometry；`param_exprs`、semantic/topology delta详情也仍是planned capability。未来增加cross-link时只能使用明确且结构验证通过的provenance，不能根据名称或geometry proximity猜测对应关系。一个operation node可以没有可见entity，也可以对应多个definition/occurrence/entity，这是正常状态。

### 19.5 Selection Service

Selection service通过toolbar显式选择`component|solid|face|edge|vertex` intent，并将triangle face groups、CAD edge groups和runtime vertex points的hit解析为：

- Scene occurrence。
- Part/assembly definition。
- Component path。
- Solid/face/edge/vertex entity。
- Source graph output。
- Engine geometry classification/properties。
- Evaluated semantic bindings/tags 和 JSON-safe SDK metadata。

Selection toolbar 必须始终显示当前 intent `component|solid|face|edge|vertex`，不能用一次 click 同时产生五个隐式 selection。Inspector展示当前实现可用的occurrence/definition/entity identity、properties、source、tags和metadata；选中的occurrence/entity在viewport高亮。World-space point/axis/bounds是runtime derived view，并标记derived；sidecar中的definition-local values保持不变。Viewer可以生成`UNIQUE QL SELECTOR` convenience text，但它不是canonical selection identity或自动持久化command。

### 19.6 Connector Editor

Connector panel 列出 selected definition 的 evaluated connector snapshots，并可在`provenance_matched` pair上进入create mode。Create mode只允许`connector_binding_status="supported"`的face、edge或vertex target；其他entities仍可选择和inspect，但panel显示exact status reason。预览使用entity`sdk_connector_frame`显示local/world axes，收集stable connector ID、nullable name和face/edge flip，然后生成第14.4节的`ConnectorBindingSpec`；vertex固定`flip=false`。

Static build 提供 download command；hosted mode 提交给明确配置的 backend endpoint。Panel 必须显示 target definition 及 occurrence count、pending/accepted/conflict 状态、新 model hash 和 scene revision。`scene_only`、`mismatched`、unbound/imported entity、assembly without supported owner operation 都是 disabled state，并给出具体原因。

### 19.7 Workspace Store

Workspace 与 loaded scene revision 分开保存。Scene revision 改变后：

- 仍存在的 stable node IDs 保留 visibility/selection preference。
- 不存在的 IDs 被 invalidated 并产生 diagnostic。
- Entity selection 只有在 entity asset/content identity 和 entity ID 仍匹配时保留。
- 禁止 geometry-nearest 自动替换 critical semantic selection。

## 20. Viewer MVP 功能边界

### 20.1 必须完成

- 加载validated `.scene.zip` package；没有embedded model时保持scene-only fallback。
- Orbit、pan、zoom、fit-to-view。
- Assembly/product tree。
- Embedded model Features tree、完整node params、assignment targets和operation summary。
- Manifest-declared完整Python source display、originating line range highlight/scroll和`call_text` fallback。
- `component`、`solid`、`face`、`edge`、`vertex` 五种 selection intent。
- Hide/show、isolate 和 reset visibility。
- Basic material color 和 stable shading。
- CAD edge overlay。
- Entity inspector：engine geometry properties、graph/topology provenance、tags、SDK metadata。
- Bounds、axes 和 grid。
- Scene/asset validation error UI。
- Display scene/source/revision information。

独立external model/unpacked loading、完整pair-state UI、parameter expressions和viewport/entity/Features双向定位属于后续扩展，不是当前MVP完成条件。

### 20.2 推荐进入 MVP 后半段

- Section/clipping planes。
- Exploded view。
- Approximate measurement，并明确精度等级。
- Named views。
- Screenshot/export image。
- Semantic tag/filter panel。
- Connector binding command authoring；hosted apply 可以在后续 milestone 接入。

### 20.3 非 MVP

- Browser-side CAD replay。
- Browser-side arbitrary feature/parameter editing。
- Constraint editing。
- Multi-user collaboration。
- Physics simulation。
- Arbitrary animation timeline。
- Texture authoring。
- General-purpose game scene scripting。
- Exact BRep measurement without backend/kernel。

## 21. Incremental Scene Protocol

第一阶段先完成 immutable full snapshot。Patch protocol 只能建立在 stable scene IDs、asset hashes 和 strict revision validation 已经完成之后。

建议后续 message envelope：

```json
{
  "protocol_version": "1.0",
  "message_type": "snapshot",
  "scene_id": "gearbox-demo",
  "revision": "sha256:...",
  "base_revision": null,
  "sequence": 1,
  "message_id": "uuid",
  "payload": {}
}
```

Patch 至少支持：

- `upsert_definition`
- `remove_definition`
- `upsert_node`
- `remove_node`
- `set_transform`
- `set_visibility`
- `set_appearance`
- `add_asset`
- `remove_asset_reference`

Patch contract 必须定义：

- `base_revision` optimistic concurrency。
- Atomic transaction boundary。
- Idempotency。
- Duplicate/out-of-order message handling。
- Missing asset behavior。
- Hash mismatch behavior。
- Reconnect 后 full snapshot resync。

不建议直接使用无约束 JSON Patch。Typed scene operations 更容易做 referential integrity validation，也能区分 transform-only update 与 geometry replacement。

## 22. Validation 与安全

Scene 文件可能由网络或用户上传，必须比当前内部 model replay 更严格。

### 22.1 Schema Validation

必须验证：

- Required/unknown fields policy。
- Semantic version 格式和 capability compatibility。
- ID 唯一性和合法字符。
- Parent、definition、asset、appearance、entity、connector 和 `SelectionRef` 全部存在。
- Top-level/definition/node/entity/connector/appearance source matrix、root IDs、graph IDs和manual source IDs满足第8.1/11/14.3节。
- Model connector source node具有正确add/forward op、slot、owner/connector params和direct inputs；trusted compiler另验证replayed equality和lineage。
- Node hierarchy 无环。
- Rigid transforms 有效。
- Bounds finite 且 min <= max。
- Asset byte length 和 hash 一致。
- `source_files`按path排序且唯一，project-relative `.py` path archive-safe且无case-insensitive collision，URI exact等于`sources/<path>`。
- Python source member是strict UTF-8，length/hash匹配；project-relative operation mapping解析到embedded file，source span等于`call_text`，`callsite_id`可重算，unresolved source要求`path=null`。
- Entity face/edge ranges 不越过对应 `(mesh_index, primitive_index)` 的 index accessor。
- Triangle indices 不越过 vertex buffer。
- Triangle/line GLB 的 scene、node、mesh、primitive、buffer 和 accessor 数量与 allowlist profile 一致。
- GLB accessor type、component type、primitive mode、coordinate conversion 与 scene contract 一致。
- Entity adjacency、source-kind agreement、face/edge range partition、alignment 和 deterministic ordering 满足 contract。
- Revision 可重新计算。

### 22.2 Resource Budgets

Loader必须在分配payload-sized memory、inflate或GPU upload前应用resource profile。Base默认untrusted-input profile固定为：

| Resource | Default maximum |
| --- | ---: |
| ZIP members | 50,000 |
| Input archive bytes | 256 MiB |
| Canonical stored archive bytes | 256 MiB |
| Total declared uncompressed bytes | 1 GiB |
| One member / one GLB | 256 MiB |
| `scene.json` | 32 MiB |
| One entity sidecar | 64 MiB |
| Embedded `model.json` | 64 MiB |
| Presentation JSON | 8 MiB |
| Decompression ratio per member and aggregate | 100:1 |
| JSON nesting depth | 64 |
| One JSON string UTF-8 bytes | 1 MiB |
| One URI UTF-8 bytes | 1,024 |
| One structural ID UTF-8 bytes | 4,096 |
| Definitions / nodes | 25,000 / 100,000 |
| Geometry / edge / entity assets | 25,000 each |
| Embedded Python source files | 25,000 |
| Appearances / connectors / cameras | 25,000 / 100,000 / 1,000 |
| Scene hierarchy depth | 256 |
| Forwarded connector chain depth | 64 |
| Entities per sidecar / total | 500,000 / 2,000,000 |
| Triangle vertices per asset / total | 2,000,000 / 10,000,000 |
| Triangles per asset / total | 2,000,000 / 10,000,000 |
| Line vertices per asset / total | 2,000,000 / 10,000,000 |
| Line segments per asset / total | 2,000,000 / 10,000,000 |
| Static decoded-buffer cost | 512 MiB |

MiB是`1024 * 1024`bytes。`input archive bytes`是transported complete ZIP byte length，不是member sizes之和，只由packed importer preflight验证；unpacked input没有该指标。Compression ratio定义为sum uncompressed member sizes / complete input archive length，且per-member ratio是uncompressed size / max(1, compressed size)。Archive preflight必须使用central/local header中一致的declared sizes累加并checked-arithmetic；实际inflate bytes必须恰好匹配declared size且仍受streaming counter限制。

Canonical exporter和packed importer都必须在materialize canonical output前精确计算`canonical_stored_archive_bytes = 22 + sum(76 + 2 * ascii_name_byte_length + payload_byte_length)`；该式适用于第15.2节zero-extra/zero-comment local header、central header和EOCD profile。值必须`<=256 MiB`且所有entry counts、sizes、offsets和central directory fields必须适配non-ZIP64 widths。这样canonical export总能被同一Base profile重新import；一个accepted deflated input即使original archive小于256 MiB，也只有在其canonical stored representation同样不超过256 MiB时才被接受。GLB header/chunk lengths还必须适配unsigned 32-bit GLB fields。

`static decoded-buffer cost`是artifact-derived validity formula，不依赖implementation residency：对每个unique triangle GLB加`position.byteLength + normal.byteLength + index.byteLength`的CPU copy和同值GPU copy；对每个unique line GLB加`position.byteLength + index.byteLength`的CPU/GPU copies；对每个vertex entity另加runtime point-picking`12` position bytes + `4` entity-index bytes的CPU/GPU copies；再加所有immutable JSON/text member uncompressed byte lengths一次。Python source使用general one-member/package limits，不使用64 MiB embedded model专用上限，并计入member count、total uncompressed、canonical archive和static immutable cost。Total使用checked uint64 arithmetic且必须`<=512 MiB`。Scene occurrences不重复计asset buffers；implementation临时parse/staging copies不影响artifact validity，但仍受process sandbox memory limit。Renderer可以lazy load降低实际residency，不能用lazy behavior接受超过static formula的package。

Browser model/DAG display另固定默认：model artifact最多64 MiB、100,000 operation nodes、500,000 dependency edges、100,000 expression nodes、graph depth 10,000。Base annotations固定为0；extension必须定义额外count budget。Implementations可以由trusted deployment显式提高limits，但不得降低schema/identity/hash检查，且UI必须显示active profile。Compiler/exporter和Python/TypeScript importers的默认tests必须使用上述同一profile。

Load/decode deadline是operational policy而不是artifact validity，因为wall-clock结果不deterministic。Viewer默认每个worker task 30 seconds并支持AbortSignal/cancellation；timeout产生workspace error，不写入manifest diagnostic。Streaming progress必须在compressed read、inflate、hash、JSON/GLB validation和GPU upload阶段报告。

### 22.3 Package Security

- 拒绝 ZIP path traversal。
- 拒绝 absolute path。
- 默认拒绝 external URI。
- 不执行 package 内脚本。
- Embedded `.py`只作为inert UTF-8 text解码和escaped source display；不得`eval`、import、注入raw HTML或发送给Python runtime。
- 使用 budgeted parser 在交给通用 renderer loader 前 preflight GLB。
- 拒绝 GLB 中的 nested/external/data URI、images、textures、animations、skins、morph targets、sparse accessors、`extras` 和未声明 extension。
- Renderer loader 的 network/file URI resolver 必须禁用，即使 preflight 有遗漏也不能发起子资源请求。
- Hash verification 必须在 GPU upload 前完成。

### 22.4 Model Replay Service

若未来服务端接受 `model.json` 并生成 scene，还必须增加 model payload budgets、kernel replay timeout、worker isolation 和 cancellation。Scene Viewer 本身不应执行 model operations。

## 23. 现有 Model Serializer 的前置加固

本地 runtime 直接编译 scene 不必等待所有 model serializer 问题修完，但以下问题会阻塞“上传 model -> 服务端生成 scene”的受信边界：

1. Model import 对 required fields 和 nested graph schema 的验证不完整。
2. Graph `edges` 和 node `inputs` 是两份 dependency representation，当前没有一致性检查。
3. `output_count`、`leaf_ids` 和部分 cross-graph refs 缺少完整 import-time validation。
4. Derived registries/logs 没有全部从 graph 重建或交叉验证。
5. 当前随机短 graph/node IDs 不适合跨独立 build 的长期 scene identity。
6. 缺少 canonical model digest；Scene 1.0 暂时只能使用 exact source artifact bytes hash。
7. 缺少 payload、node count、depth、kernel time 和 memory budgets。
8. 缺少正式 migration registry 和 historical fixtures。

这些工作与 Scene Schema 并行，但在开放不可信 model upload 前必须完成。

## 24. 测试策略

### 24.1 Scene Schema Tests

- Minimal valid standalone shape scene。
- Valid nested assembly scene。
- The same valid/malformed corpus is accepted/rejected by Python and TypeScript with matching JSON Pointer/code。
- Duplicate/missing IDs。
- Parent cycles 和 dangling parent。
- Missing definition/asset/appearance ref。
- Invalid/non-finite transforms。
- Wrong revision/hash。
- Unknown field policy。
- Required/optional/nullable matrix for every base record and discriminated union variant。
- Stable caller-provided `scene_id`; missing `scene_id` fails without fallback。
- Version compatibility matrix。
- RFC 8785 vectors cover Unicode keys/strings、IEEE-754 rendering、negative zero and two-pass revision omission。
- Default and boundary `compile_options`、safe-integer limits、resource profile limits。

### 24.2 Compiler Tests

- One `Solid` -> one root-aware shape definition、one root occurrence、one geometry asset、one edge asset 和 one entity asset。
- One `Part` -> product definition、material mapping、provenance。
- Nested `Assembly` -> correct local hierarchy。
- Same Part repeated N times -> one mesh asset、N instance nodes。
- Same subassembly repeated -> stable expanded occurrence paths。
- Flattened Compound -> no invented product hierarchy。
- Placement-only change -> same geometry asset hash。
- Material-only change -> same geometry asset hash。
- Geometry/tessellation change -> new asset hash。
- Part connectors -> evaluated definition-local connector snapshots。
- Existing closed-edge/unresolved connector causes explicit compilation failure rather than omission。
- Model runtime-only metadata mismatch with clean replay fails；replayed metadata remains deterministic。
- Flattened Compound owner tags/metadata have one definition-level projection and are not copied to child solids。
- Exact source artifact repeated with reversed/shuffled kernel traversal -> same entity、GLB and scene hashes。
- Symmetric/coincident entities -> canonical bytes remain stable and ambiguous connector selectors are not marked supported。
- Empty root、empty assembly、wire/shell/face-only root、任一collapsed face和completely empty line asset fail explicitly；individual collapsed edges remain degenerate inspector-only entities。
- Unsupported root value fails explicitly。
- Imported Part/Assembly或缺失stable `source_element_id`的imported root fails explicitly；缺少primitive mapping的imported entities remain `unbound`。
- `embed_source=true`写入exact `model/model.json`和sorted `source_files`，每个`sources/<project-relative-path>`的bytes/hash/length保持一致。
- 同graph ID但不同graph object的root、越界output slot和创建后被mutate的stale `ModelResult` snapshot全部fail closed。
- `@model(export_dir=...)`和`ModelResult.export_artifacts()`只写一个`<graph_id>.scene.zip`，不旁置写model/session JSON、STEP、STL或FCStd。

### 24.3 Mesh Tests

- Positions/normals finite。
- Indices valid。
- Triangle orientation consistent。
- Bounds match vertices。
- Face groups exactly partition expected index ranges。
- Every face and rendered edge has exactly one positive range；degenerate edges have no range and expose an inspector-only entity。
- CAD edge polylines are not triangle boundaries。
- Deterministic GLB bytes across repeated exports。
- Triangle and line writers reproduce normative exact-byte GLB vectors and hashes。
- Round-trip GLB decode preserves counts and bounds。

### 24.4 Picking Tests

- Component pick resolves scene node。
- Repeated instances share asset but return distinct occurrence IDs。
- Solid intent resolves owning solid from a face hit。
- Face group resolves graph/node/output source and optional proven topology evidence without conflating them。
- Edge group resolves source edge。
- Vertex point pick resolves definition-local entity and occurrence-specific world point。
- Entity inspector returns engine geometry/properties, tags and JSON-safe SDK metadata。
- Trusted compiler binding/tag caches match runtime source; browser only claims artifact-proven target evidence for `model_topology`。
- Revision change invalidates stale selection safely。

### 24.5 Embedded Model Provenance 与未来 Connector Tests

- Embedded model在用于Features前完成byte-length/hash、schema version、graph ID、node shape、inputs、leaf IDs和output references cross-check。
- Reformatting otherwise equivalent model JSON会改变Scene 1.0 exact-byte artifact hash。
- Scene-only package保持Preview/tree/entity selection，Features/source disabled。
- Future external model slot必须覆盖`artifact_matched`、`provenance_matched`、`model_only`和`mismatched` states，且非matched状态不能启用provenance cross-link或connector command drafting。
- Binding spec stale model hash、scene revision、entity asset、entity source or duplicate connector ID fails atomically。
- `model_output` binding requires exact source scene recompilation and unique ephemeral entity resolution; no nearest-geometry fallback。
- Selector tie/unstable replay produces non-supported `connector_binding_status` and cannot draft a command。
- Forwarded snapshot validates direct source component、source definition/snapshot ownership、offset composition and acyclic depth。
- Missing source model/presentation/root output/toolchain profile prevents `cad_verified` capability。
- Backend without editable model transaction rejects apply even for a direct-root Part。
- Backend with future editable transaction still rejects nested immutable Part apply until nested Product rewrite capability is advertised。

### 24.6 Package Tests

- Packed and unpacked scene equivalence。
- Missing asset。
- Corrupt GLB。
- Hash mismatch。
- ZIP traversal。
- Duplicate/colliding ZIP member、backslash/NUL name、encrypted/non-regular entry 和 central/local header mismatch。
- ASCII case-insensitive collision、data descriptor、ZIP64、multi-disk、extra/comment and unsupported method rejection。
- Duplicate JSON object key、BOM、invalid UTF-8 和 trailing token。
- Missing/wrong `source_files` member、unsafe path、wrong URI、case-fold collision、source hash/length mismatch和invalid UTF-8。
- Embedded operation source unknown/missing field、unmapped project-relative path、span mismatch和wrong `callsite_id`。
- Packed extraction/unpacked directory symlink escape。
- Zip bomb/resource budget。
- External URI rejected by default。
- Canonical exporter reproduces exact archive bytes, order, timestamps, modes and CRC metadata。

### 24.7 Viewer End-to-End Fixtures

至少保留以下 immutable fixtures：

- Single colored bracket。
- Repeated bearing balls 或 repeated fasteners。
- Nested reducer assembly。
- Large integrated actuator。
- Symmetric part with ambiguous topology identities。
- Scene with named view 和 appearance override。

每个 fixture 保留：

- Exact source model artifact hash。
- Scene manifest golden snapshot。
- Canonical `scene.json` bytes、revision vector、asset bytes/hashes and canonical archive hash。
- Expected node/definition/triangle counts。
- Entity/connector snapshot counts、provenance variants、binding status、DAG linkage 和 five-intent picking assertions。
- Features tree selection、assignment-target display、完整source file、active line range、scroll和unresolved-source fallback assertions。
- Reference screenshot tolerance test。

## 25. 实施阶段

### Phase A：Scene Contract 与 Characterization

状态：已冻结并由Python/TypeScript shared corpus、generated types、exact JCS/GLB/ZIP vectors和strict validators持续验证。

工作项：

- 定义 immutable scene dataclasses。
- 提交五个structural JSON Schema 2020-12 files、normative semantic rule registry和generated Python/TypeScript types。
- 提交两个normative profile JSON、hash-linked numeric/canonicalization pseudocode和profile schemas/validators。
- 定义strict manifest/package/sidecar/spec validators和canonical JSON encoder。
- 定义 ID、revision、coordinate system 和 URI policy。
- 定义 Entity Snapshot、evaluated connector 和 `ConnectorBindingSpec` exact records。
- 定义 `ScenePresentationSpec` schema 和 deterministic no-presentation defaults。
- 定义exact triangle/line GLB skeleton、default resource profile和canonical ZIP envelope。
- 实现只接受`Mapping[str, bytes]`的low-level canonical ZIP envelope encoder/decoder；它不理解scene manifest，只负责Phase A exact headers、ordering、CRC、budgets和vectors。
- 为现有 examples 记录 expected product hierarchy 和 mesh counts。
- 明确 private `TriMesh` 与新 `RenderMesh` 的边界。
- 增加shared valid/malformed corpus、JCS/revision vectors、exact-byte GLB vectors和ZIP metadata vectors。
- 增加current Model Schema 2.0 topology coverage、reversed traversal、symmetric entity和selector ambiguity characterization tests。

退出标准：

- `scene-1.0.schema.json`、`entities-1.0.schema.json`、`presentation-1.0.schema.json`、`connector-binding-1.0.schema.json`和`normalized-product-1.schema.json`全部closed并通过schema metaschema validation。
- `scene-1.0-rules.json`、`scene-1.0-ocp-glb-2.profile.json`、`ocp-evaluated-properties-1.profile.json`及其linked pseudocode全部通过applicable schema、content-hash linkage和unknown-field validation。
- Minimal/nested/repeated-instance scene能在Python和TypeScript构造或parse、验证和round trip。
- 两端对全部shared valid/malformed fixtures给出相同accept/reject结果及稳定JSON Pointer/error code。
- 相同scene重复序列化得到相同canonical bytes/digest；golden JCS和two-pass revision vectors逐byte通过。
- Python/TypeScript GLB preflight接受triangle/line exact-byte vectors并拒绝每个forbidden-member mutation。
- Python/TypeScript low-level archive preflight接受exact canonical ZIP vector、逐field mutations和allowlisted deflate fixture；low-level envelope encoder逐byte重现ZIP vector。
- Default/resource/numeric边界、entity adjacency/range、provenance union、forwarded connector和binding status matrices有golden coverage。
- 只有以上条件全部满足，文档和schemas才能从`Proposed`改为`Frozen`；实现PR不能自行放宽contract。

### Phase B：Scene Compiler 与 Render Assets

状态：当前slice已能从runtime values生成canonical `.scene.zip`；model publishing profile嵌入`model/model.json`和mapped Python source。

工作项：

- 实现 `compile_scene`。
- 实现`SceneRoot`内Solid/Compound/Part/Assembly traversal。
- 实现 definition/instance deduplication。
- 实现第10.2节`set_model_metadata_rvalue` exact operation并纳入Model Schema 2.0 export/import/replay和translator capability registry；将stdlib和Phase B fixtures中的post-operation `set_metadata()`迁移到该operation，使clean replay投影与runtime exact相等。
- 实现 `RenderMesh`、`RenderEdgeMesh`、normals 和 bounds。
- 实现 deterministic triangle/line GLB writer 与 standard glTF coordinate conversion。
- 实现 definition-specific entity snapshot、engine properties、SDK tags/metadata 和 face/edge picking ranges。
- 实现 evaluated connector snapshots。
- 将Phase A low-level envelope codec集成为scene directory/ZIP exporter/importer；增加manifest/member/hash/GLB/entity validation，不另写ZIP header implementation。
- 实现operation source mapping、`source_files` collection和embedded model/source cross-validation。
- 实现`@model(export_dir=...)`与`ModelResult.export_artifacts()`的single-package publishing path。

退出标准：

- Example 10和当前model exporters可以生成validated self-contained package；其余保留examples按支持范围持续characterize。
- Repeated part 只产生一个 geometry asset。
- Placement-only changes 不改变 asset hash。
- CAD edge asset 不是 triangle boundary derivation，且能够通过 line pass 加载。
- Triangle/line writer逐byte重现Phase A vectors；canonical ZIP exporter逐byte重现archive vector。
- Same exact inputs在fresh processes和reversed traversal characterization harness中产生相同scene、entity、GLB和archive hashes。
- Full package validator拒绝hash/range/adjacency/profile/budget/forwarded-connector mutations before renderer consumption。

### Phase C：Viewer MVP

状态：独立`viewer/` TypeScript/Three.js/Vite slice已在不运行CAD replay的情况下加载`.scene.zip`，显示evaluated scene、embedded Features和Python source。

工作项：

- Validated package loader和content-hash checks。
- Orbit/pan/zoom/fit。
- Product tree。
- Features tree、node params、assignment targets和source range display。
- Component/solid/face/edge/vertex selection intent。
- Visibility/isolate。
- Basic appearance。
- GPU edge overlay。
- Entity/geometry/tag/metadata inspector。
- Error/diagnostic UI。
- 后续：external model/unpacked loaders、完整pair states、expressions和provenance-backed双向cross-link。

退出标准：

- 大型 Example 20 可以加载、导航、选择和 isolate components。
- Embedded model package的Features/source pane与scene viewport同时可用；scene-only package保持geometry capability。
- Feature/source browser-level automation补齐line highlight和scroll regression。
- Missing/corrupt assets 显示结构化错误，而不是白屏。

### Phase D：CAD Interaction

目标：从通用 mesh viewer 进化到可用 CAD viewer。

工作项：

- Section/clipping。
- Exploded view。
- Semantic tag/filter inspection。
- Approximate measurement 与 precision labels。
- Named views 和 screenshots。
- Selection provenance panel。
- Connector binding command UI；backend apply 等待 editable model transaction capability。

退出标准：

- 用户可以从 component -> solid/face/edge/vertex -> source graph/semantic evidence 完成追溯。
- 用户可以选择 supported topology entity、预览 connector frame 并生成 validated binding command。
- Viewer 明确区分 exact 和 mesh-approximate measurement。

### Phase E：Publishing 与 Incremental Updates

目标：支持 hosted scene、cache 和 transform/material 增量更新。

工作项：

- Scene snapshot protocol。
- Typed patch operations。
- Revision conflict/resync。
- Content-addressed asset service。
- Browser persistent asset cache。
- Worker-side model replay isolation。

退出标准：

- Transform-only patch 不重新下载 geometry。
- Duplicate/out-of-order patch 可检测并恢复。
- Reconnect 能通过 full snapshot 正确 resync。

### Phase F：Exact CAD Services 与 Kinematics

目标：在保持 thin Viewer 的前提下增加高级 CAD 能力。

可选工作项：

- Backend exact measurement/query API。
- Optional BRep sidecar。
- Assembly joint projection 和 motion preview。
- LOD、streaming 和 mesh compression。
- Feature history linkage。
- Annotation publishing。
- Nested Product graph rewrite for connector apply。

这些能力不是 Viewer MVP 的前置条件。

## 26. 里程碑与优先级

| 优先级 | 里程碑 | 直接产物 |
| --- | --- | --- |
| P0 | Scene Schema + validator | 稳定 contract、canonical digest、malformed tests |
| P0 | Runtime Scene Compiler | `SceneRoot[Solid|Compound|Part|Assembly]` -> `CompiledScenePackage` |
| P0 | RenderMesh + triangle GLB | Browser-ready geometry、normals、bounds |
| P0 | CAD edge asset | Line GLB、正确 edge overlay、基础 edge provenance |
| P0 | Entity snapshot + five-intent picking | Viewer 与 CAD provenance/metadata 的桥梁 |
| P0 | TypeScript/Three.js package viewer | Camera、render、tree、Features/source、selection、inspector、asset reuse |
| P1 | External model pairing + E2E harness | Pair states、bidirectional provenance、source highlight browser regressions |
| P1 | Section/measure/explode | 基础 CAD inspection UX |
| P1 | Connector binding command | Topology selection 到 revision-bound authoring command |
| P1 | Persistent browser cache | 跨会话 asset reuse |
| P2 | Scene patch protocol | 增量更新和 hosted viewer |
| P2 | Exact backend services | Analytic measurement/query |
| P2 | Kinematics projection | Motion preview |

## 27. Viewer MVP 总体验收标准

以下条件全部满足，才可称为首个可用 Viewer，而不是 mesh demo：

1. Viewer 加载 scene 时不需要 SimpleCAD Python runtime 或 OpenCascade。
2. Scene 保留 Assembly/Component/Part hierarchy，不只是一块 flattened mesh。
3. Repeated part instances 共享 geometry asset。
4. Component、solid、face、edge、vertex selection 可以追溯到 scene occurrence、entity snapshot 和 source provenance。
5. Viewer 支持product tree、Features/params、selection、hide/show、isolate和fit-to-view。
6. CAD edge overlay 不显示 triangle 内部边。
7. Scene、GLB 和 entity snapshot sidecar 都有 strict validation 和 content hash。
8. Large assembly 的 asset loading 有明确 budgets、progress 和 error state。
9. Scene IDs、revision 和 asset IDs 的含义不同且被测试固定。
10. Workspace state 不污染 canonical model 或 scene。
11. Viewer 若提供 mesh measurement，必须明确标记为 approximate；Phase C MVP 可以尚未提供 measurement。
12. 同一exact source artifact、resolved roots、presentation、compile options、profile bytes、registered `toolchain_hash`和完整`generator` record重复导出得到deterministic scene revision和asset hashes。
13. Scene-only package保持geometry capability；embedded model package增加Features/source capability。Future external pair states需要另行满足`artifact_matched`、`provenance_matched`、model-only和mismatched测试。
14. Entity inspector 显示 engine properties、topology provenance、tags、metadata 和 connectors，不依赖 browser OCP replay。
15. 选择mapped feature时显示assignment targets和完整manifest-declared Python file，高亮originating range且不执行source code。

## 28. 风险与取舍

### 28.1 Scene 与 Model 信息重复

Scene 必然复制一部分 evaluated state，例如 transforms、material color 和 semantic tag cache。解决方式不是消除所有重复，而是明确 canonical owner、source artifact hash 和 invalidation。Scene 是可丢弃 build artifact；不可重建的 authored presentation 由 `ScenePresentationSpec` 拥有。

### 28.2 Topology Identity 不够稳定

当前 `topo_id` 和随机 operation node IDs 不能保证跨独立 build 稳定。Scene 1.0 只能保证同一 model revision 内 picking 可追溯。跨 revision selection persistence 优先依赖 product path 和 semantic bindings；无法证明时应失效。

### 28.3 GLB 与 CAD 坐标习惯不同

Scene 固定 `+Z` up 和 mm，GLB 固定遵守 glTF 2.0 meter/`+Y` up，`asset_to_scene` 保存唯一转换。不能让不同 exporter 自行选择 axis/unit，否则 transform、measurement 和 picking 会分裂。

### 28.4 Viewer 过早依赖具体前端框架

Scene contract、GLB 和 entity snapshot sidecar 应独立于 Three.js、Babylon.js 或其他 renderer。Frontend 可以替换，scene schema 不能由某个 framework object serialization 决定。

### 28.5 一开始设计完整游戏引擎 Scene

SimpleCAD 需要的是 CAD evaluated scene，不是脚本、physics、audio、particle、arbitrary ECS。Schema 应保留 extension/capability 机制，但第一阶段只实现 CAD Viewer 必需的 hierarchy、renderable、appearance、camera 和 annotation。

### 28.6 Scene 自动附加到每个 ModelResult

自动编译会显著增加每次model build的tessellation、内存和序列化成本，也隐藏质量参数，因此不能成为`@model`的无条件副作用。当前实现采用显式opt-in：`@model(export_dir=...)`在调用结束后自动发布，省略`export_dir`时保持in-memory-only；`ModelResult.export_artifacts(output_dir=...)`提供调用后的显式替代。两个入口都只写一个self-contained `.scene.zip`。

## 29. 推荐决策

1. 新增独立 Scene Schema 1.0，不扩展 Operation Graph 为 render scene。
2. `model.json` 继续是 design/replay canonical artifact；scene 是 evaluated、可重建的显示 artifact。
3. `capture_result`不承担scene visibility或hierarchy；low-level `compile_scene(scene_id=..., roots=...)`显式提供logical scene identity和roots，automatic publishing wrapper只从explicit captured outputs派生roots。
4. 使用 Definition/Instance 分离，保留 assembly hierarchy 和 repeated mesh reuse。
5. 使用`.scene.zip` package。Generic render package包含`scene.json`、content-addressed triangle/line GLB和definition-specific entity sidecar；self-contained model package还包含`model/model.json`和`sources/<project-relative-path>`。
6. Scene 使用右手 `+Z` up、mm 和 parent-relative rigid transforms；GLB 保持标准 glTF meter/`+Y` up。
7. Render mesh 与 collision mesh 分离；新增 normals、CAD edges、typed entity snapshots 和 picking ranges。
8. Product material 与 render appearance 分离，RGB 只做确定性默认映射。
9. Product path 是 scene occurrence identity 的首选，asset bytes 使用 SHA-256 identity。
10. Viewer workspace、`ScenePresentationSpec` 和 evaluated scene 分离。
11. 首先完成 immutable full snapshot，再设计 patch protocol。
12. Browser Viewer 不执行 model replay；不可信 model replay 放在有 budget 和 isolation 的后端 worker。
13. Mesh Viewer 的 measurement 默认为 approximate，exact CAD measurement 通过后端或 optional kernel 提供。
14. Scene schema、compiler、asset writer和entity/picking contract先于高级frontend能力；独立`viewer/`在validated package上逐步扩展pairing、provenance和panels。
15. Connector authoring 使用 revision-bound command，由 SDK/backend 更新 canonical model并重编 scene；不能直接修改 evaluated snapshot。
16. Operation source mapping是只读Viewer evidence，不执行代码，也不成为feature selection的第二canonical owner。

## 30. 建议的下一步

Phase A、compiler/exporter、source embedding和Viewer基础slice已经落地，下一步集中处理剩余边界：

1. 为Viewer加入不依赖手工操作的browser E2E fixture，验证package upload、Features selection、assignment targets、完整source display、line range highlight和scroll。
2. 明确当前package-only loader与未来external model/unpacked loader的产品边界，再实现pair-state UI和provenance-backed双向cross-link。
3. 完成presentation/imported source compilation或将相关public types继续标记为contract-only。
4. 继续以shared corpus保持Python/TypeScript validator parity，新增每个source mapping/path/member trust-boundary mutation。
5. Connector command UI可以围绕schema实现；backend apply仍必须等待editable model transaction，nested Product rewrite不做隐式兼容。
