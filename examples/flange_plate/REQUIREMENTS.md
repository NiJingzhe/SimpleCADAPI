# Requirements: flange_plate（参数化法兰盘）

- Inputs: 用户 prose（全部尺寸已给定；几何体素路线由用户指定）+ 一轮批量提问（2026-09-05，用户预先批准按上稿选定全部默认）
- Functional goals:
  1. 参数化法兰盘：盘 + 中心凸台 + 中心通孔 + 均布螺栓通孔阵，所有控制尺寸走命名参数（`scad.var`，带单位注释）
  2. 两次圆角：凸台根部 R3、法兰外缘上下 R2；圆角前必须打印选边卡（QL resolve 数量 + 边长），选边失败显式失败
  3. 参数可行性守卫前置（不可行参数在建模前显式 assert 失败，不许静默产出坏几何）
- Geometry targets（分区描述，已确认）:
  1. **法兰盘**：⌀`flange_od`(100) × 厚 `flange_t`(10) 圆柱盘；盘底平面 z=0，+Z 向上。
  2. **中心凸台**：⌀`boss_od`(55) 圆柱，自盘顶面 z=`flange_t` 起，凸台顶面到盘底距离 `boss_top_z`(30)（凸台高出盘面 20）。
  3. **中心通孔**：⌀`bore_d`(30)，轴线 = Z 轴，贯穿盘 + 凸台。
  4. **螺栓通孔阵**：`bolt_count`(6) × ⌀`bolt_d`(11)，轴线平行 Z，均布于 PCD `bolt_pcd`(78)，首孔位于 +X（0°），贯穿法兰盘厚度（不含凸台）。
  5. **圆角**：凸台根部（凸台柱面 ∩ 盘顶面交线圆）R`boss_fillet_r`(3)；法兰外缘上、下两条交线圆各 R`edge_fillet_r`(2)。
- Units / coordinate convention: mm；原点 = 法兰轴线 ∩ 盘底平面；+Z 向上（凸台方向）；受控基准面：盘底 z=0、盘顶 z=`flange_t`、凸台顶 z=`boss_top_z`；轴对称（关于 Z 轴，孔阵除外按 `bolt_count` 旋转对称）。
- Named parameters (Var):
  - `flange_od = 100`（法兰盘外径, mm）
  - `flange_t = 10`（法兰盘厚度, mm）
  - `boss_od = 55`（凸台外径, mm）
  - `boss_top_z = 30`（凸台顶面到盘底距离, mm）
  - `bore_d = 30`（中心通孔直径, mm）
  - `bolt_d = 11`（螺栓孔直径, mm）
  - `bolt_pcd = 78`（螺栓孔分布圆直径, mm）
  - `bolt_count = 6`（螺栓孔数）（USER 第 2 轮改参：6 → 8，PCD 78 → 守卫可行值）
  - `boss_fillet_r = 3`（凸台根部圆角, mm）
  - `edge_fillet_r = 2`（法兰外缘圆角, mm）
  - `min_edge_web = 2` ASSUMED default（轮辐宽下限：螺栓孔边到法兰外缘的最小筋宽；取 = `edge_fillet_r`，保证外缘圆角不吃穿孔边）
- Fastening & mounting: 螺栓沿 −Z/+Z 双侧可装（通孔、平孔口、无沉头）；中心孔为轴/管道过孔。
  Envelope math: `bolt_d`=11 → 轮辐宽 = `flange_od`/2 − `bolt_pcd`/2 − `bolt_d`/2 ≥ `min_edge_web` →
  **PCD 上限 = `flange_od` − `bolt_d` − 2·`min_edge_web` = 100 − 11 − 4 = 85**
- Service conditions: 未声明（不做强度/FEM 断言）
- Export targets: `examples/out/flange_plate/` 下 .scadpkg + STEP + STL + 4 张渲染图（iso/front/top/detail）
- Verification intent（验收前已写定，全部走外置 verify 脚本）:
  - V1 (S1): 单实体、正体积；bbox = ⌀100 × [0, 30]±0.05；体积 = π/4·(flange_od²·flange_t + boss_od²·(boss_top_z−flange_t) − bore_d²·boss_top_z) ±0.5%
  - V2 (S2): 螺栓孔 `bolt_count` 个 ⌀11 圆柱孔壁 @PCD（QL 卡片：半径、圆心到轴距离）；根部 torus ×1（R3）；外缘 torus ×2（R2，上下）；仍单实体；体积 < S1 体积
  - V3 守卫: 源码 `assert_params()` 含 4 条守卫（中心孔<凸台、轮辐宽、孔与根部圆角不干涉、根部圆角≤凸台高）；verify 脚本以 known-bad 参数探针证明守卫承重（拒绝时抛错）
  - V4 (改参轮): PCD 88 须被轮辐宽守卫拒绝并打印依据；推导最大可行 PCD（保轮辐宽）；按可行值交付 8 孔版并重跑 V1/V2 回归 + 守卫判定证据
  - V5 (导出): .scadpkg 新进程重开校验；STEP/STL 非空；4 渲染图存在；隔离 reviewer 按形状描述逐区域 match/mismatch/unreviewable 判定
- Ask-or-Record ledger（本轮为批量预答：已问（批量）→ 用户预答（按上稿），不再向真实用户重复提问）:
  | item | asked/assumed | answer/value |
  | --- | --- | --- |
  | 螺栓孔轴线与头侧 | asked（批量预答） | 沿 Z 贯穿、平孔口无沉头/倒角，双侧可装（按上稿选定） |
  | 基准与坐标 | asked（批量预答） | 盘底 z=0、+Z 凸台方向、原点在法兰轴线（按上稿选定） |
  | 螺栓孔起始角 | asked（批量预答） | 首孔 +X（0°）均布（按上稿选定） |
  | 载荷/服务工况 | asked（批量预答） | 未声明，仅做几何验证，不做强度断言（按上稿选定） |
  | min_edge_web 数值 | assumed | 2 mm（= edge_fillet_r；轮辐须不小于外缘圆角半径，改参轮据此推导 PCD 上限） |
  | 螺栓规格推断 | assumed | ⌀11 ≈ M10 + 1mm 间隙（孔径用户给定，规格为推断，不影响几何） |

## USER 第 2 轮改参（2026-09-05）：8 孔 + PCD 尽量大（88）

守卫判定链（verify/s3_guard_evidence.py，证据原样可复跑）:
1. **8 孔 @PCD 88 → G2a 拒绝**：web = 100/2 − 88/2 − 11/2 = 0.500 < min_edge_web = 2.0
2. **上确界 85 → G2b 排除（实征退化）**：web(85) = 2.0 == edge_fillet_r，孔口圆与 R2 圆角切圆
   精确内切。实跑 8×PCD85：边圆角吞并相切 0° 孔壁（孔壁 7/8、faces 16≠17、体积反常 +950、
   顶/底面中心偏移 +X）——相切是真实失败模式，非理论洁癖。守卫据此拆分：
   G2a 轮辐宽 ≥ 下限；G2b web 严格 > edge_fillet_r（禁相切）
3. **交付 8 孔 @PCD 84.5**（0.5mm 网格上严格可行最大值，web=2.25，裕度 0.25）：
   G1 wall 12.5>R3 / G2a 2.25≥2 / G2b 2.25>2 / G3 gap 6.25>0 / G4 boss_h 20≥R3 全过

参数变化：`bolt_count` 6→8（间距 60°→45°）；`bolt_pcd` 78→84.5；其余全部不变。
（几何回归：s2_verify D1-D5 全 PASS @8 孔 84.5 版。）

（USER 第 2 轮改参需求原文见 session_transcript.md [2] USER；判定记录同步 BUILD_PLAN.md S3 节。）
