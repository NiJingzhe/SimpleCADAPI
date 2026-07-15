# PDF 证据、术语与引用索引

上级索引：[README.md](README.md)

## 1. 资料身份

- 源文件：`../50376-2014-Labanieh四轴向最新结构中文版(1).pdf`
- 布局包：`../50376-2014-Labanieh四轴向最新结构中文版(1).layout/`
- PDF 页数：15 页，对应原论文页码 34 至 48。
- SHA-256：`e56700751e12ffe36f94f1a7b46d7cccec02d8fa0f030302e52800f5d879dbc8`
- 布局 schema：`termpdf.layout.v1`

## 2. TermPDF 对象引用

稳定引用格式：

- `p5`：PDF 第 5 页页面对象。
- `p5.t10`：第 5 页第 10 个文本行对象。
- `p5.t3-p5.t10`：同页连续文本对象范围。
- `[PDF 图3.23: p5; p5.t10]`：图形位于页面 `p5`，图题对象为 `p5.t10`。

图形没有单独的图片对象引用，因此机械图统一用“页面对象 + 图题对象”定位。正文事实用文本对象范围定位。

检索示例：

```bash
termpdf grep "图 3.23" "../50376-2014-Labanieh四轴向最新结构中文版(1).layout"
```

## 3. 证据级别

| 级别 | 定义 | 使用规则 |
|---|---|---|
| PDF 明示 | 原文或图中直接给出的结构、数量、动作或顺序 | 可以作为方案事实 |
| 图示还原 | 根据机构图的零件位置、箭头和相邻正文还原 | 必须保留图引用，CAD 中需要验证 |
| 工程化补全 | 为制造、装配、传动、安全或维护新增的内容 | 必须明确不是原论文参数 |

## 4. 术语统一

中文版存在机器翻译和 OCR 误差，设计文档统一使用以下术语：

| PDF 中出现的表达 | 本设计使用 | 英文含义 |
|---|---|---|
| 毛线纱 | 经纱 | warp yarn |
| B轴纱、偏置纱、偏压纱 | 偏斜纱 | bias yarn |
| 粘合纱、绑定纱 | 粘合纱 | binder yarn / Z-yarn |
| 填充纱 | 填充纱 | filling yarn / weft |
| 拉皮尔、剑针、短剑 | 拉剑 | rapier |
| 啮合杆、接线杆 | 接合杆 | engaging rod |
| 簧片、芦苇、梳齿 | 开放式筘 | open reed |
| 收卷 | 直线牵引 | linear take-up |
| 导引块、偏心导块 | 偏斜纱导向块 | bias yarn guide block |

## 5. 关键正文证据

| 主题 | PDF 对象 | 事实摘要 |
|---|---|---|
| 多轴多层目标 | `p1.t3-p1.t23` | 采用对称 `+θ/-θ` 层和厚度方向增强，减少卷曲并提高抗分层能力 |
| 独立经纱筒子 | `p1.t26-p1.t31` | 每根经纱独立供给并带张力补偿 |
| 固定经纱导向 | `p2.t10-p2.t14` | 经纱穿过固定光滑圆孔，无传统综框交错 |
| 移动偏斜供纱链 | `p2.t15-p2.t21` | 偏斜筒子装在旋转链上，每步对应一次输送 |
| 四个偏斜层 | `p3.t3-p3.t6` | 两个框架形成四层偏斜纤维层 |
| 导向块闭环换位 | `p3.t20-p3.t31` | 四根横移杆、两根升降杆、三个驱动阶段、每周期一步 |
| 偶数框架与对称 | `p4.t3-p4.t7` | 框架数量应为偶数，形成中面对称结构 |
| 两组粘合针 | `p6.t12-p6.t20` | 针组位于织物两面并交替，插入位置影响纱线弯曲和断裂 |
| 拉剑与接合杆 | `p7.t22-p7.t28` | 拉剑带回双股纱圈，接合杆 1 升降，接合杆 2 前后加升降 |
| 三个填充通道 | `p8.t3-p8.t18` | 上、中、下三个通道由三根拉剑同步填充 |
| 开放式筘 | `p10.t20-p10.t36` | 筘片单侧固定，按上升、前进、下降、后退四步运动 |
| 边缘收缩问题 | `p11.t9-p11.t23` | 偏斜纱折叠产生向中心收缩力 |
| 边缘挂钩 | `p11.t24-p11.t28`、`p12.t3-p12.t4` | 每周期左右各插入挂钩，并随织物沿特殊导轨移动 |
| 直线牵引 | `p12.t5-p12.t7` | 厚织物不用旋转卷布，夹具由长螺杆直线移动 |
| 两次填充周期 | `p13.t12-p13.t18` | 每个完整周期需要两次填充插入 |
| 完整工艺顺序 | `p13.t21-p13.t29`、`p14.t3-p14.t28` | 从插钩、偏斜索引到两次填充、打纬和牵引 |

## 6. 图 3.20 至图 3.36 索引

| 图号 | 内容 | 页面 | 图题对象 | 主要专题 |
|---|---|---|---|---|
| 图 3.20 | 整机等轴测图 | `p2` | `p2.t9` | [01](01-process-and-system-architecture.md)、[02](02-spatial-layout-and-envelopes.md) |
| 图 3.21 | 筒子张力补偿 | `p3` | `p3.t19` | [03](03-yarn-feeding-and-bias-indexing.md) |
| 图 3.22 | 偏斜供纱链 | `p4` | `p4.t13` | [03](03-yarn-feeding-and-bias-indexing.md) |
| 图 3.23 | 偏斜导向块定位机构 | `p5` | `p5.t10` | [03](03-yarn-feeding-and-bias-indexing.md) |
| 图 3.24 | 导向块三个换位状态 | `p5` | `p5.t20` | [03](03-yarn-feeding-and-bias-indexing.md)、[07](07-timing-interlocks-and-control.md) |
| 图 3.25 | 上下导向框架层序 | `p6` | `p6.t11` | [01](01-process-and-system-architecture.md)、[02](02-spatial-layout-and-envelopes.md) |
| 图 3.26 | 粘合针工作位置 | `p6` | `p6.t33` | [04](04-insertion-beating-and-binder-mechanisms.md) |
| 图 3.27 | 粘合针可用间隙 | `p7` | `p7.t15-p7.t16` | [04](04-insertion-beating-and-binder-mechanisms.md) |
| 图 3.28 | 玻纤弯曲断裂 | `p7` | `p7.t21` | [04](04-insertion-beating-and-binder-mechanisms.md)、[09](09-materials-tolerances-and-validation.md) |
| 图 3.29 | 织造区等轴测图 | `p8` | `p8.t26` | [04](04-insertion-beating-and-binder-mechanisms.md) |
| 图 3.30 | 填充插入五步 | `p9` | `p9.t11` | [04](04-insertion-beating-and-binder-mechanisms.md)、[07](07-timing-interlocks-and-control.md) |
| 图 3.31 | 三个填充通道 | `p10` | `p10.t18` | [02](02-spatial-layout-and-envelopes.md)、[04](04-insertion-beating-and-binder-mechanisms.md) |
| 图 3.32 | 筘四步运动 | `p11` | `p11.t8` | [04](04-insertion-beating-and-binder-mechanisms.md)、[07](07-timing-interlocks-and-control.md) |
| 图 3.33 | 宽度收缩对比 | `p12` | `p12.t9` | [05](05-width-control-and-linear-takeup.md) |
| 图 3.34 | 偏斜纱收缩力 | `p12` | `p12.t19` | [05](05-width-control-and-linear-takeup.md) |
| 图 3.35 | 挂钩与直线牵引 | `p13` | `p13.t10` | [05](05-width-control-and-linear-takeup.md) |
| 图 3.36 | 完整周期时序 | `p15` | `p15.t28` | [07](07-timing-interlocks-and-control.md) |

## 7. 使用边界

- PDF 没有给出精确轴径、轴承、齿数、材料牌号、速度和负载。
- 图中比例只能用于相对关系，不能直接量取制造尺寸。
- OCR 中 `θ`、`0`、正负号和术语可能混淆，设计判断应同时看图和上下文。
- 工程建议值进入加工图前必须由 [09-materials-tolerances-and-validation.md](09-materials-tolerances-and-validation.md) 中的实测项目闭合。
