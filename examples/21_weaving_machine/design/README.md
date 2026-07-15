# 四轴向多层织机设计文档索引

本目录把机械方案按设计责任拆分。每篇文档可以独立评审，同时通过相对链接共享上下文。该专题集是设计方案的唯一维护入口；原始 PDF 和 TermPDF 稳定布局包位于上一级目录。

## 输入资料

- [原始 PDF](../50376-2014-Labanieh四轴向最新结构中文版(1).pdf)
- [TermPDF 布局包](../50376-2014-Labanieh四轴向最新结构中文版(1).layout/)
- PDF SHA-256：`e56700751e12ffe36f94f1a7b46d7cccec02d8fa0f030302e52800f5d879dbc8`

## 文档地图

| 文档 | 单一责任 | 主要读者 |
|---|---|---|
| [00-evidence-and-terminology.md](00-evidence-and-terminology.md) | PDF 对象引用、证据级别、术语和图索引 | 所有人 |
| [01-process-and-system-architecture.md](01-process-and-system-architecture.md) | 目标织物、工艺边界、系统任务分割和总体参数 | 系统设计、工艺 |
| [02-spatial-layout-and-envelopes.md](02-spatial-layout-and-envelopes.md) | 三维坐标、工作平面、层高、纱线及机构包络 | 总体 CAD、运动仿真 |
| [03-yarn-feeding-and-bias-indexing.md](03-yarn-feeding-and-bias-indexing.md) | 经纱供料、偏斜供纱链、导向块和三阶段索引 | 供纱与导向机构设计 |
| [04-insertion-beating-and-binder-mechanisms.md](04-insertion-beating-and-binder-mechanisms.md) | 粘合针、三层拉剑、接合杆和开放式筘 | 织造区机构设计 |
| [05-width-control-and-linear-takeup.md](05-width-control-and-linear-takeup.md) | 边缘挂钩、特殊导轨、夹具和直线牵引 | 成型与牵引设计 |
| [06-transmission-interfaces-and-dynamics.md](06-transmission-interfaces-and-dynamics.md) | 轴系、机械接口、载荷路径和动力学配合 | 传动、结构计算 |
| [07-timing-interlocks-and-control.md](07-timing-interlocks-and-control.md) | 十步周期、主相位、局部凸轮相位、互锁和故障状态 | 运动、电控、安全 |
| [08-parts-assembly-and-cad-breakdown.md](08-parts-assembly-and-cad-breakdown.md) | 独立零件几何、装配副、尺寸链、总成树和装配顺序 | CAD、工艺、装配 |
| [09-materials-tolerances-and-validation.md](09-materials-tolerances-and-validation.md) | 材料、公差、调试、验收和待定参数 | 制造、试验、项目管理 |
| [10-bottom-up-cad-implementation-plan.md](10-bottom-up-cad-implementation-plan.md) | 自底向上建模工作包、代码边界、完整性关口和测试矩阵 | CAD 开发、机械设计、验证 |

## 依赖关系

```text
00 证据与术语
├── 01 工艺与系统架构
│   ├── 02 空间与包络
│   ├── 03 供纱与偏斜索引
│   ├── 04 织造执行机构
│   └── 05 控宽与牵引
├── 06 传动与动力学 ← 03 + 04 + 05
├── 07 时序与互锁   ← 02 + 03 + 04 + 05 + 06
├── 08 零件与装配   ← 02 + 03 + 04 + 05 + 06
├── 09 材料与验证   ← 全部专题
└── 10 CAD 实施计划 ← 00 至 09
```

## 设计状态

- 当前是机械结构与传动原理方案。
- 已实现 `REPRESENTATIVE/HOME` 整机 CAD：A00 至 A90 十四个稳定顶层总成全部在场，包括主机架、经纱/偏斜供纱、上下导向框、M1 锁相传动、粘合针、三层拉剑、接合杆、开放式筘、控宽挂钩和双丝杠直线牵引；同时保留参数/证据合同、inventory、姿态/累计状态、纱线身份守恒、D0 零件和 D1 单节距夹具。可见纱线和成型体几何已省略，避免将工艺参考误认为机械零件。运行和输出边界见 [../README.md](../README.md)。
- 当前 `REPRESENTATIVE/HOME` 的 369 个可见叶零件全部通过实体几何支承审计：在 `0.25 mm` 固定接触容差下，只允许同一 A 级总成内部或该总成到 A10 的接触边，并要求连续回到 A10 两条纵向基准梁。该结果证明当前姿态的几何支承链，不替代紧固件、刚度、强度、疲劳或动态接触验证。
- 当前整机是概念级代表性 HOME 几何，不是已验证的完整功能机、加工图、电气原理图或控制程序。未闭合的重复数量按代表性实例降采样，GAP-02/GAP-03 仍阻止 A40/A41/A42 功能闭合、连续凸轮规律、`FULL` 和制造发布。
- PDF 没有给出精确尺寸、载荷、轴承、电机和材料牌号；文档中的此类数值均标为工程建议值。
- 参数骨架、代表性功能 CAD 和验证框架可以使用明确标识的工程建议值启动；真实重复数量、纱线接触件、传动选型和加工图必须在对应参数冻结后发布。
- 参数进入加工图前必须通过 09 的计算、样件和公差闭合关口；L0 至 L5 无纱分级验证在穿目标纤维前完成。

## 建议评审顺序

1. 阅读 00 和 01，确认 PDF 事实、术语和目标织物。
2. 评审 02，冻结整机坐标、工作平面和机构禁入区。
3. 并行评审 03、04、05 三组机械子系统。
4. 用 06 完成轴系和载荷闭环。
5. 用 07 建立运动仿真状态机。
6. 用 08 建立 CAD 总成和独立零件。
7. 用 09 制定制造、调试和验收计划。
8. 按 10 从参数合同、D0 数字零件和 D1 运动副合同开始，自底向上实施；物理 L0 至 L5 仍严格按 09 验收。
