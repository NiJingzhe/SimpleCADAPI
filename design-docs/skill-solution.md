# Skill×Model 协同失效分析与修复方案

日期：2026-08-22 · 来源：`session-audit-01a02469.md`（session `01a02469`，弓形把手建模，4h22m 未完成）· 改动目标：`docs/skill/`（skill 层源文件；打包镜像 `skills/simplecadapi/references/`，由 skill-pack 同步）。

**范围判定**：只整理审计归因矩阵中 **Skill 流程 与 模型能力 同时在因** 的条目（P1–P8，见 §0）。P9（25 次 edit 锚点损坏）归因 harness/模型，与 skill 文本无关，排除；审计 §3 的 SDK 主因项（fillet 无回显、渲染无自动取景等）skill 侧只能缓解，单列 §5 边界表，不在本方案内冒充可根治。

---

## 0. 问题总览

| 审计编号 | 问题 | Skill 归因 | 模型归因 | 配合失效一句话 |
|---|---|:-:|:-:|---|
| P1 | 0 次澄清、孔向错两次、工况后置 2h | ● | ●● | 规则写着"fit matters 时问那一个问题"，模型自行判定"fit 不 matters"——裁量权在模型，gate 无产物 |
| P2 | API 页读了仍按错误契约调用 | ○ | ●● | 页面存在但无"读页=提取签名/返回值/前置条件"的动作定义，浅读无拦截 |
| P3 | zoom 手调 39/47、highlight 0/47 使用 | ○ | ●● | 工作流验收只有一句 "Visual plausibility"，无最小视角集、无高亮步骤 |
| P4 | 26 条错边 fillet 静默成功；姿态验证当安装验证 | ● | ●● | validation gate 只查体积/BRep/尺寸，不查"选中集正确性"，也不约束"验证证明什么" |
| P5 | 安装性五轮试错全靠用户兜底 | ● | ●● | brief 必答清单与 mechanical-modeling 均无"紧固件包络→最小几何"前置条目 |
| P6 | QL 明文规则 3h55m 零使用；上手后仍缺反馈 | ●● | ●● | "not arbitrary topology indexes" 只在 discipline 页一句 prose，无默认范式、无反模式点名、无 onboarding 代码块 |
| P7 | 四次"已完成"被同一张参考图驳回 | ○ | ●● | 无交付前对照清单（视角集/并排/局部放大），也无"单参考图时索要多视角或尺寸"的规则 |
| P8 | FEM 有敏感性无判决；后续与几何改动脱钩 | ○ | ● | boundaries 只规定"没跑分析不得声称强度"，没规定"跑了分析必须给判决" |

排除：P9（edit 锚点机制）——harness 工具层，skill 文本无法作用。

---

## 1. 三条配合失效模式（根因归纳）

P1–P8 表面是八个独立问题，底层是三条可复用的失效模式。修复方案（§4）逐条对准它们：

**M1 读而不做。** 规则以 prose 存在、被读过，但不产生任何强制产物。审计中最重的两条都是此类：
- `requirement-refinement.md` L56-58（"ask the one scaling question when fit matters"）被读两次（审计 L9/L483），全程 `ask=0`，30 轮用户发言中 21 轮纠错；这是一个非常严重的问题，我们需要有一种更严的手段确保模型真的进行了需求的分析和边界的设计。
- `geometric-validation.md` L42-43（"not arbitrary topology indexes"）开题即读（审计 L18），QL 首次真实使用在 L2000（3h55m 后，且由用户点名触发）。QL 作为一种核心能力实际上应该在 skill 和 SDK 的实现上都更加注意的。他应该成为一种核心工作模式。
教训：**prose 规则不改变模型行为；只有绑定"必打印/必渲染/必填字段"的产物要求才改变。**

**M2 默认范式缺位，模型退回本能。** skill 不给出可复制的正确写法时，模型走最小阻力路径——全部有实证：
- 选边本能 = 索引（`get_edges()[0],[2]`，L1972）与阈值窗口（`abs(x-lx)<12`，L641）；
- 取景本能 = zoom 枚举（3.0→5.0 连猜，39/47 次）与 20+ 张 probe 图；
- 修圆角本能 = candidate_sets × radius 暴力枚举 + `except: pass` 吞错（L929-930）；
- 基数本能 = `.exactly(N)` 硬猜再改数（expected 8 got 12、expected 2 got 4）。
教训：**禁令挡不住本能；范式（copy-paste 代码块）才能成为新的最小阻力路径。** 这里就有很多值得优化的点了。我们需要在 skill 里提供 通用的 常见选择意图 -> QL 的可复制的例子。

**M3 自评即通过，无证据产物。** "操作成功"被当成"效果符合预期"：
- fillet 内核返回成功实体 = 圆角正确（26 条错边事故，L926）；
- "8 个带 `face.arc_handle.root_blend` 标签的生成面" = 圆角落在正确的边上（L981——标签面数只证明操作发生）；
- 最终姿态零碰撞 = 可安装（L1139/L1191 两次"验证通过"的模型实际装不进螺栓，轴向扫掠包络 163.8mm³ 碰撞，L1214）；
- 读了渲染图 = 看了图（L1949 宣告成功，L1954 才看见两端大缺口）。
教训：**验收必须要求可核查的证据类型（选中集卡片、扫掠包络检查、视角命名清单），自评陈述不算证据。** 这里另一点是指：验证边界必须是在 需求进入的时刻就被明确的 确定性边界（视觉除外，因为视觉只能靠 agent 来评估，这时候可以确定的 call 具有干净上下文的 sub agent）

---

## 2. 逐项取证与 skill 现状缺口

以下行号：`L<N>` = 审计 JSONL 行号；skill 文件行号 = 当前 `docs/skill/`（与打包镜像逐字节一致，已 diff 验证）。

### 2.1 P1 澄清 gate：规则存在、无强制、裁量判错

**审计证据**：开题 20 秒出简报（L29）；参考图无尺寸直接取经验值（孔距 140、沉头 2.4×孔径，L124）；孔方向错两次（L417、L466）；固定方式与载荷由用户 15:08 主动给出（L1317）才进模型——此前 2 小时的耳盘/耳厚/沉头深度决策全部无受力依据，工况给出后 FEM 立即暴露 250N 下 2.32mm 变形不可接受（L1511）。全程 `ask=0`。

**skill 现状**：`domains/requirement-refinement.md` L75-87 "Clarification policy" 把"是否 fit-critical"的判定交给模型；L81-83 虽列出 ask 触发条件（"no dimensions and no scale reference"、"safety/load-critical"），但没有强制产物——模型可以读完后自行得出"不必问"。brief 必答清单（L19-32）有 units/features/positioning/validation targets，**无安装方式、无载荷方向**两个本例致命项。

**缺口判断**：规则正确但形式是"裁量+prose"。沉头孔 + 无尺寸参考图明明命中 L81 两条 ask 条件，模型仍判为不必问——证明裁量路径不可靠，需要把裁量改成 Ask-or-Record 二选一。

### 2.2 P2 API 页读法：读了页、没读契约

**审计证据**：调用不存在的 `Solid.is_closed()`（L614）——而 `geometric-validation.md` L25 明写 "`Solid` has no public `is_valid()` method"，同页读过两次；跑旧 example 导出 STEP 而非 SDK 导出入口（L1374，用户 L1388 点破，`export_product_package_to_step.md` 存在但 L1397 才首次读）；gmsh `getNodes()` 三元组按二元解包（L1457，外部 API 未查文档）。

**skill 现状**：`SKILL.md` 阅读顺序规定"每个用到的 API 读其确切页"，但没有定义"读页"这个动作的输出。`part-modeling.md` L50 说 "Read the exact page ... for every API used"，同样无动作定义。SDK 外依赖（gmsh/CalculiX/VTK）不在任何页面的责任边界内。

**缺口判断**：○ 级——页都在，缺"读页=提取签名/返回值/失败模式"的契约，以及外部 API 的文档责任声明。注意 `is_closed` 事故证明**重复写明单个陷阱无效**（写了两处仍踩），有效的是流程化的读法动作。

### 2.3 P3 视觉验证：一句 "Visual plausibility" 兜底一切

**审计证据**：47 次渲染中 39 次手填 zoom 枚举；`highlight_tags`/`tag_labels`/`show_callouts` 全程 0 次使用（grep 证实），直接后果是"选错 26 条边仍以为成功"无工具性拦截（与 P4 连锁）；首张图相机沿把手端向、压成 C 形不可用（L377）；多视角纪律靠用户逐图教育（L2030）才建立"局部放大斜视+剖切+侧视"三图标准；FEM 云图 `SetScaleFactor` 次序 bug 两图同错（L1582-1594）。

**skill 现状**：`workflows/single-part-modeling.md` L82-83 验收门仅一句 "Visual plausibility: proportions, wall thickness vs overall size, feature positions vs edges"；`geometric-validation.md` L73-79 有"视觉关注点转为确定性检查"的原则（方向正确），但没有**交付前视觉证据的最小集**。`render_screenshot_rpath.md` 签名含 `highlight_tags`（L6）但 Description 空——签名存在不构成使用引导。

**缺口判断**：验收门从"看起来合理"改为"枚举的视角清单+高亮图"。zoom 自动取景属 SDK 缺陷（§5-2），skill 侧只能规定"zoom 由 bbox 推导并记录所用视角"。

### 2.4 P4 选中集回验 + 验证定义：本审计最致命一类

**审计证据**：
- (a) 26 条非目标边 fillet 成功无告警（L926）；修复=暴力枚举+吞错；以标签面数为证据（L939/L981）；同类选边失效 ≥6 次（L451/L1019/L1628/L1747/L1972）。
- (b) 验证定义错：姿态交集通过 ≠ 可安装，用户教三步（圆柱→锥头→轴向插入扫掠，L1099/L1154/L1202），第三次才暴露 163.8mm³ 碰撞；反向又犯——删掉让位切削只留验证包络（L1954），用户立原则"包络必须参与切割"（L1957）。
- (c) 用户反馈"handler 遮住孔"被解读为设计意图并实现（L1009→L1011），两次驳回（L1093/L1097）——透视遮挡与实体侵入未区分，而可判定的实验（孔内圆柱测交集）要等用户提出。

**skill 现状**：`geometric-validation.md` 的 gate 覆盖 validity/volume/尺寸测量/replay，**无选中集正确性检查**；L73-79"视觉关注→确定性检查"原则恰好能覆盖 (b)(c)，但没有"验证前先声明验证证明什么"的协议，也没有"路径 vs 姿态"的判例。`failure-and-repair.md` fillet 失败类（L49-58）只讲"失败怎么办"，不讲"成功但选错怎么办"——而本事故是后者。

**缺口判断**：两处缺口——detail 操作前的选中集证据 gate；(b)(c) 类"验证定义"协议。这是 skill 侧 ●、可与模型 ●● 叠加的最强配合点。

### 2.5 P5 安装性前置：约束后置 4 小时

**审计证据**：安装性从未进设计输入，五轮方向修正全部用户驱动（时间线见审计 §P5）；"杆根偏置 = 5.4 + 8.5 + 1.5 = 15.4mm" 这类装配约束算式 L1962 才首次出现——在用户 L1957 立原则之后。

**skill 现状**：brief 必答清单无装配/紧固项；`mechanical-modeling.md` 有 datum/参数/比例 sanity，**无"紧固件包络→最小几何"推导要求**。`manufacturing-boundaries.md` L24 有 M3/M5 间隙孔默认值（说明紧固件尺寸知识已存在），但没有接到造型前置约束。

**缺口判断**：● 级 skill 缺条目。修复=把包络算式作为 brief 输入要求，而非干涉检查失败后的补丁。

### 2.6 P6 QL：明文规则无 enforcement、无范式、无 onboarding

**审计证据**：L1977 用户点名前零使用；上手后立刻暴露断层：谓词命中 3 条边但无"可能是接缝"反馈（L2000-2003）；选对边 ≠ 几何可行（0.5mm 环带，L2006）；`shared_boundary(..., to_kind="edge")` 一次选中真实根边（L2016）——正确抽象存在但由用户口述启用（L2008）；融合+圆角后标签丢失退回几何谓词（L2078-2081）；基数连错两次（L2051/L2066）。**会话最终死在这一步**（最后 40 分钟在修 QL 选边函数，无交付）。

**skill 现状**：`geometric-validation.md` L42-43 选择纪律一句 prose + L44-52 标签/索引说明；workflow 步骤 5（L56-60）说 "print small QL-derived facts" 但无一句可复制代码。`shared_boundary` 不在任何 workflow/discipline 页出现（只在自动生成 API 页）。反模式（索引选边）未点名禁止——L44-45 甚至说 indexed getters 是 "for intentional picks"，给模型留了合理化空间。

**缺口判断**：●● 级。三件事都缺：默认范式（shared_boundary 优先）、反模式点名、基数/命中探针的固定写法。SDK 侧反馈缺失（无命中预览/溯源）单列 §5-3。

### 2.7 P7 交付判断：无对照清单、无参考图纪律

**审计证据**：四次"已完成"被同一张 1568×1176 无尺寸参考图驳回（+9min、+27s、看图即驳、continue 后自见缺口）；视觉对照验收方式本身是用户 13:17 引入的（L341），此前"验证"只有体积/面数/BRep；参考图始终一张，助手从未索取正交视图或尺寸。

**skill 现状**：workflow Deliverables（L95-98）要求列出 "QL validation facts actually printed, assumptions made, and checks not run"（好），但**无交付前视觉对照清单**；refinement 的 input precedence 处理"图无尺寸怎么办"，但不处理"单视角参考图不够怎么办"。

**缺口判断**：○ 级。修复=交付清单加视觉证据项 + refinement 加"单参考图时可索取正交视图/关键尺寸"。

### 2.8 P8 FEM 判决：跑了的分析没有结论

**审计证据**：做对的部分见审计 §P8（材料声明、载荷分级、网格敏感性、原始表核对）；缺失：597MPa 峰值 vs PVC 屈服 45-55MPa 相差一个数量级，报告从未回答"行不行"——无许用应力/安全系数判决；L1841 后结构再设计与 FEM 完全脱钩，应力集中位置未反馈进任何再设计。

**skill 现状**：`manufacturing-boundaries.md` L38-52 完整规定"几何不能证明强度、没跑分析不得声称"——但**跑了分析之后输出什么没有规定**。判决层（峰值 vs 许用 → 安全系数；位移 vs 功能限 → pass/fail）是空白。

**缺口判断**：○ 级。补一段"分析报告必须以判决结尾"，并把"FEM 复跑与几何改动绑定"写进 workflow 修复路由。

---

## 3. 修复方案总则

对准 §1 三条失效模式，所有方案遵守：

1. **规则→产物**：每条关键规则绑定一个可打印/可渲染/可填写的 artifact（brief 字段、选中集卡片、checklist 勾选）。没有产物的规则视为未修复。
2. **范式优先于禁令**：给可复制的正确写法（代码块/表格），把正确路径变成最小阻力路径；禁令只在反模式造成过实际事故时点名（本审计即事故库）。
3. **不新增路由目标**：所有插入进现有 workflow 已加载的页面（`README.md` 授权规则：cross-cutting 能力由 workflow 拉入，不做路由目标）。P6 的教训双向成立——`geometric-validation.md` 在阅读路径内仍不被执行（位置不是充分条件），但不在路径内的页面必然白写（位置是必要条件）。
4. **skill 文本不承诺 SDK 没有的能力**：自动取景、fillet 选中回显、QL 命中溯源等归 §5 SDK 侧；skill 只写模型自己能做的补偿动作。

---

## 4. 方案 S1–S8

每项给出：对准失效模式、改动文件（`docs/skill/` 源）、插入内容草案（英文，贴近现有页文风；`→` 表示插入位置）。落地后需 skill-pack 重新打包同步镜像。

### S1 Refinement：Ask-or-Record gate + brief 补安装/载荷字段 【对准 M1/P1、P5】

**改动文件**：`docs/skill/domains/requirement-refinement.md`、`docs/skill/discipline/requirement-and-cad-brief.md`（同步改）。

1. "The brief must answer" 清单追加两项（L32 "Validation targets" 前）：

```text
- Mounting and service conditions when the part fastens to anything or
  carries load: fastener type/size, head side and insertion direction,
  mounting face, and the load direction with a magnitude class.
```

2. "Clarification policy" 节（L75-87）改写为 Ask-or-Record——裁量改二选一，允许一次问全：

```markdown
## Clarification policy (Ask-or-Record)

When any blocking item below is missing, it is either asked (batched
into one question set before any geometry) or recorded in the brief as
a reported assumption. Proceeding with neither — a silent default — is
the failure mode, not the asking.

Blocking items:

| Missing item | Blocks when |
| --- | --- |
| One overall dimension / scale anchor | reference is images only and any physical fit matters |
| Fastener axis and head side | holes, counterbores, or countersinks are present |
| Mounting face / mating interface | the part attaches to anything |
| Load direction and magnitude class | the part carries load (structural role) |

Batch all blocking questions into one ask; four one-question round
trips are worse than one four-question ask. Ask when: no dimensions and
no scale reference for a physical object; a mating interface is
described but unspecified; the part is load-critical; output depends on
a missing source file. Do not ask when a default clearance or cosmetic
radius suffices, or the user asked for a first-pass concept.
```

3. `requirement-and-cad-brief.md` "The one-question rule"（L56-60）加一句判例："Discretion failed here: an image-only brief with countersunk mounting holes was modeled for hours without asking, and was rejected twice on hole orientation alone."

**机制**：把"问不问"从模型裁量改为产物检查——brief 里每个 blocking 项要么有答案要么有显式假设，审计中"0 ask + 21 轮纠错"的路径被堵死。

### S2 Validation：选中集证据 gate（detail 操作前）【对准 M3/P4(a)、P6】

**改动文件**：`docs/skill/discipline/geometric-validation.md`（"Selection discipline" 节后新增）。

```markdown
## Selection evidence gate (before fillet/chamfer)

A detail operation succeeding proves the kernel built a solid — not
that the right edges were selected. Filleting 26 unrelated edges
returns a valid solid. Before every `fillet_rsolid`/`chamfer_rsolid`:

1. Print the selection card: count, and for each edge its length and
   center (faces: center and area). Read it — a seam edge or a neighbor
   feature inside the window shows up here as an unexpected hit.
2. Assert the cardinality you designed for (`.exactly(n)`), where n
   comes from feature intent, never from adjusting n until the call
   succeeds.
3. When the selection carries tags, render it once with
   `render_screenshot_rpath(..., highlight_tags=[...])` and state the
   view used. Seeing the selected edges is the check.

Anti-patterns, each a documented silent-wrong-part delivery:
- Index picks (`get_edges()[i]`) for edges you did not create and name
  in this step — booleans and fillets renumber topology.
- Enumerating candidate edge sets x radii with `except: pass`; a hit
  confirms the selection is uncontrolled, it does not solve it.
- Counting generated `face.*` tag faces as proof the blend landed on
  the intended edges — tag-face count proves the operation ran, not
  where.
```

**机制**：fillet 成功不再是证据；卡片+基数断言+高亮图三个产物缺一不可。直接对准 L926/L939/L981/L2051/L2066 全部事故形态。

### S3 QL：边选择默认范式（copy-paste）【对准 M2/P6】

**改动文件**：`docs/skill/discipline/geometric-validation.md`（"Selection evidence gate" 后）、`docs/skill/workflows/single-part-modeling.md` 步骤 5（L56-60）引用之。

```markdown
## Edge-selection defaults

In order of preference:

1. Blend between two named bodies -> intersection semantics:
   `ql.shared_boundary(body_a, body_b, to_kind="edge")` — the real
   shared boundary, not a geometric window approximating it.
2. Role surface -> tag predicate on the `role.*` tag attached when the
   feature was created.
3. Geometric window (last resort) -> bounded predicate on
   normal/center/length, printing every hit's center and length before
   use (this is the selection card).

Index getters are for intentional picks you can name in this step —
never for discovering which edges to blend.
```

同时 `workflows/single-part-modeling.md` 步骤 5 末尾加一行：

```text
   Select detail edges per the edge-selection defaults in
   `discipline/geometric-validation.md` (shared_boundary first);
   run the selection evidence gate before every fillet/chamfer.
```

**机制**：M2 的解法——正确写法成为路径上最省力的选项。`shared_boundary` 从"用户口述才发现"变为 workflow 直接点名。基数探针固定写法（卡片）已在 S2，互为支撑。

### S4 Validation：验证定义协议（三问 + 反馈转谓词）【对准 M3/P4(b)(c)】

**改动文件**：`docs/skill/discipline/geometric-validation.md`（"Spec-driven measurement" 前新增节）。

```markdown
## Define what the check proves before writing it

1. Posture or path? A fit/assembly claim for a fastened feature is
   proven by sweeping the fastener envelope along the insertion path
   (slide-in, rotate-in), not by intersecting the final posture.
   Final-posture clearance passing is not evidence of assemblability.
2. Verification geometry vs design geometry: if the check body also
   cuts, or a cut was removed to make the check pass, state which role
   it plays. A verification envelope that cannot coexist with the
   design validates neither. When the envelope must also machine the
   clearance, it is a design feature — treat it as one.
3. A failed check closes by changing the design, or by changing the
   check's definition with the user — never by weakening the check or
   deleting the interfering material out of the verification body.
4. Convert review feedback into a predicate before implementing it:
   "it occludes the hole in the render" -> does measured material
   intersect the hole cylinder? Run the cheap experiment that
   distinguishes occlusion from intrusion before modeling either.
```

**机制**：把审计 L1099→L1214（三步教学）、L1954→L1957（删切削）、L1009→L1011（遮挡当意图）三个事故各自的教训固化为前置三问+一转换。第 4 条把"用户反馈先复述判定实验"变成规则。

### S5 Mechanical：紧固件包络前置推导【对准 M1/P5】

**改动文件**：`docs/skill/discipline/mechanical-modeling.md`（"Sanity-check proportions" 前新增节）。

```markdown
## Fastener envelopes precede geometry

When the part has fastened or mating features, derive the controlling
minimums before modeling and carry them as named parameters in the
brief — they are inputs, not patches after an interference check
fails:

- Countersink/counterbore: head diameter + shaft + wall/clearance ->
  minimum land diameter, minimum boss thickness, minimum edge distance.
- Insertion path: envelope swept along the assembly motion -> minimum
  lateral offset between the path and any neighboring material
  (e.g. rod-root offset >= head radius + rod radius + wall).
- The envelope that guarantees assemblability usually must also machine
  the clearance: design it as a cutting feature, and keep the check on
  its result rather than on the posture alone.
```

**机制**：审计 L1962 的 15.4mm 算式在第 4 小时出现——此方案把它推到建模前的 brief 字段（与 S1 的 mounting 条目衔接）。

### S6 Workflow：视觉验收最小集【对准 M3/P3、P7】

**改动文件**：`docs/skill/workflows/single-part-modeling.md` 验收门（L82-83 替换）。

```markdown
- Visual acceptance minimum — each item produced before declaring done:
  1. whole-part views from at least two named directions (state the
     view; `auto` alone is not a direction);
  2. a close-up of every region a review comment touched, framed by a
     bbox-derived zoom estimate — re-rendering with hand-tweaked zoom
     until it looks right is enumeration, not framing;
  3. side-by-side with the reference image when one exists, and request
     an orthographic view or a key dimension when a single perspective
     reference is all there is;
  4. the selection-highlight render from the selection evidence gate.
```

配套：`docs/skill/domains/requirement-refinement.md` "Input precedence" 末尾加一行："A single perspective reference is a floor, not a spec: when fidelity matters, request an orthographic view or one key dimension rather than inferring hidden geometry."

**机制**：验收从形容词（"plausibility"）变成可勾选的产物清单；"+27 秒被驳"类事故要求第 2/3 项在场。

### S7 API 读法契约 + 外部 API 边界【对准 M2/P2】

**改动文件**：`docs/skill/README.md` "Authoring rules" 加一条 + `docs/skill/domains/part-modeling.md` "API groups" 引言行。

```markdown
- Reading an API page is an action with an output: before the first
  call of any API, note its signature, return type, and documented
  failure modes — one line each in the working notes. A method name
  absent from the page does not exist, however plausible it looks.
  Non-SDK dependencies (Gmsh, CalculiX, VTK, FreeCAD scripting) are not
  covered by SDK pages: check their own documentation before the first
  call.
```

**机制**：`is_closed` 事故证明重复陈述单个陷阱无效（两处明写仍踩）；改为流程动作（读页必留三行笔记），并对 gmsh 解包类外部 API 事故划定文档责任边界。

### S8 Analysis：跑了的分析必须以判决结尾【对准 M1/P8】

**改动文件**：`docs/skill/discipline/manufacturing-boundaries.md`（"What geometry never proves" 节后新增）。

```markdown
## When an analysis is run, it ends in a verdict

The boundary above forbids claiming strength without analysis; the
reverse also holds — analysis that was actually run must end in a
judgment, not a table:

- Peak stress vs material allowable (yield/ultimate as appropriate)
  -> state the safety factor, or state that no allowable is available
  and what would establish one.
- Peak displacement vs the functional limit -> pass/fail against the
  requirement the user named, not a bare number.
- Mesh sensitivity stated once; a geometry change that moves a loaded
  region re-runs the comparison before the change is called an
  improvement.
```

**机制**：审计 L1495 有敏感性、无判决；L1841 后 FEM 与几何迭代脱钩。此方案把判决与复跑设为报告的必输出项。

---

## 5. Skill 边界：需 SDK 根治、skill 仅缓解的项

对审计 §3 的 SDK 失败清单，skill 侧方案只能补偿，不能替代。防止 skill 文档被写成承诺 SDK 没有的能力：

| SDK 缺陷（审计 §3） | skill 侧缓解（本方案） | 根治位置 |
|---|---|---|
| 1. `fillet_rsolid` 静默成功于错误边集、无选中回显 | S2 选中集卡片+高亮图（模型自己造证据） | SDK：fillet 返回 selected-edges 报告 + before/after 面数对照 |
| 2. 渲染无自动取景/ROI、`zoom` 裸数值；`render_step_views_rpath` 段错误无降级 | S6 bbox 推导 zoom + 记录视角；可在 `failure-and-repair.md` 导出失败类加一句"VTK 渲染后端崩溃 → 降级 `render_screenshot_rpath` + 命名视角" | SDK：渲染器 auto-frame/ROI 入口 + 崩溃降级路径 |
| 3. QL 无命中预览/溯源/基数拟合提示 | S2/S3 打印命中表固定写法 | SDK：命中集高亮渲染快捷方式、基数不符时最近候选拟合 |
| 4. `apply_tag` LOCAL 作用域跨布尔/圆角丢失 | S3 范式第 1 条直接教 `shared_boundary`，绕开标签存活问题 | SDK：标签跨操作存活语义或 propagation 默认 |
| 5. 类型注解与运行时不一致（`tuple[float,...]` vs `Expr`） | 无（不可由行为规则补偿） | SDK：修注解 |
| 6. `.scadpkg` 序列化边界（Var/Expr 进 geo 元数据、旧包缺 blobs） | 无（已在 session 内修复并补回归测试） | SDK：已修，维持回归 |

---

## 6. 落地顺序与验收

**优先级**（按审计致死度排序）：
1. **S2 + S3**：P4/P6 是会话终止原因（最后 40 分钟死于 QL 选边），且选错边不被发现放大了所有其他错误。
2. **S1 + S5**：前置设计输入，砍掉"0 ask → 21 轮纠错"的整条路径。
3. **S4 + S6**：验证定义与交付证据，封住"四次宣告完成"模式。
4. **S7 + S8**：读法契约与判决模板，低频但零成本。

**改动位置**：全部在 `docs/skill/` 源文件（§4 已列）；改后 `skill-pack` 重新打包同步 `skills/simplecadapi/references/` 镜像。

**验收边界**：
- [ ] 结构断言（grep `docs/skill/`）：`requirement-refinement` 含 "Ask-or-Record" 与 mounting/load 字段（S1 落在 domains 页）；`geometric-validation` 含 "Selection evidence gate"、"shared_boundary"、"Posture or path"；`single-part-modeling` 验收门含 "Visual acceptance minimum"；`manufacturing-boundaries` 含 "ends in a verdict"。
- [ ] `uv run pytest test/test_skill_pack.py -q` 通过（引用路径校验；本方案不新增文件、不新增引用路径，风险最低）。
- [ ] 行为验证（人工，一次即可）：以审计同题 prompt（参考图 + "建模这个把手，沉头安装孔"）新开会话，检查：首个建模动作前 brief 是否含 Ask-or-Record 产物（ask 调用 ≥1 或显式假设清单）；首个 fillet 前是否出现选中集卡片；选边是否以 `shared_boundary`/tag 谓词起步而非索引。
- [ ] 对照指标：原会话 `ask=0`、QL 首用 +3h55m、四次完成宣告被驳——重放会话中三项应分别变为 ≥1、首小时内、0-1 次。

**明确不做**：不在 skill 页引用审计编号/行号（skill 面向所有用户，事故库留本文档）；不改 `SKILL.md` 路由表（不新增路由目标）；不把 §5 SDK 项写进 skill 文本。
