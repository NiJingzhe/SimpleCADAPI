# Requirements: ap242_gmsh_bracket（L 形直角连接件 · 正式化重建）

- Inputs: 用户 prose 描述（本轮原文）+ 现有参考模型 `examples/12_ap242_gmsh_volume_mesh/model.py`（legacy 脚本，作为尺寸真值来源逐项核对）+ 下游脚本 `export_fem_mesh.py` / `export_step.py` / `export_fcstd.py` / `export_obj.py` / `export_stl.py`（运行契约来源）
- Functional goals:
  1. 结构承载 L 形直角连接件：竖壁固定（fixed_support），横板承载（load_surface + load_hole），三角筋抗弯
  2. AP242/Gmsh FEM 工作流主模型：`interface.*` 面标签是下游 gmsh 物理组选面契约，必须原样保留
  3. 按 single-part-modeling 工作流 + Feature Tree Convention 正式化（特征块 + 命名参数），几何与 legacy 等价
- Geometry targets（分区，已按 legacy model.py + 实测核对）:
  1. **竖壁 wall**：box 4(X)×40(Y)×36(Z)，X∈[-2,2]、Y∈[-20,20]、Z∈[0,36]；背面平面 x=-2（法向 -X）→ `interface.fixed_support`
  2. **横板 shelf**：box 28(X)×40(Y)×4(Z)，底面中心 (12,0,0) → X∈[-2,26]、Y∈[-20,20]、Z∈[0,4]；顶面 z=4 → `interface.load_surface`（实测面积 835.7257 = 24×40 − 2×(16×3 筋底) − π·3²，质心 (14.5271, 0, 4)）
  3. **三角筋 rib ×2**：XZ 平面直角三角形，顶点 (0,·,4)/(0,·,22)/(18,·,4)——竖边高 18（贴竖壁，嵌入壁内 x∈[0,2] 保证正重叠）、水平边深 18（x 0→18 落在横板上）；厚 3，y 条带中心 y=±11（即 [9.5,12.5]/[-12.5,-9.5]）
  4. **安装孔 mount_hole ×2**：⌀5（r=2.5），轴 +X，y=±11（孔距 22），z=0.62×36=22.32，贯穿竖壁（工具越界 x∈[-3,3]）→ `interface.mount_hole_1`（y=-11）/ `interface.mount_hole_2`（y=+11）（实测孔壁面积 63.0604，孔心 (0.0075, ±11, 22.3111)）
  5. **承载孔 load_hole**：⌀6（r=3.0），轴 +Z，x=12、y=0，贯穿横板（工具越界 z∈[-1,5]）→ `interface.load_hole`（实测孔壁面积 75.3982 = 2π·3·4，孔心 (12, 0, 2)）
  6. **整体角色标签**：`role.structural_l_bracket`（实体级）
  7. legacy 实测基线（verify/legacy_baseline_facts.json + verify/legacy_interface_facts.json）：体积 10097.790499 mm³、面数 17、bbox≈[-2.004,-20,-0.004]×[26,20,36]
- Units / coordinate convention: mm；原点 = 竖壁底面中心（壁厚中面 X=0、宽度中面 Y=0、底面 Z=0）；+X 壁厚方向（背面 x=-2）；+Y 宽度方向（零件关于 XZ 面 y=0 对称）；+Z 高度方向；基面 z=0 = 竖壁/横板公共底面
- Named parameters (Var)（与 legacy 常量一一对应，全部 mm）:
  - `bracket_width = 40.0`（Y 向总宽）
  - `bracket_height = 36.0`（竖壁高）
  - `bracket_depth = 28.0`（横板 X 向深）
  - `plate_thickness = 4.0`（壁/板厚）
  - `mount_hole_radius = 2.5`（安装孔 ⌀5）
  - `mount_hole_spacing = 22.0`（孔距）
  - `mount_hole_height_ratio = 0.62`（孔高 = ratio×36 = 22.32）
  - `load_hole_radius = 3.0`（承载孔 ⌀6）
  - `load_hole_x = 12.0`（承载孔 X 位）
  - `rib_thickness = 3.0` / `rib_height = 18.0` / `rib_depth = 18.0`
  - `rib_offset_y = 11.0`（筋中心 y=±offset）ASSUMED default（legacy 字面量 11.0；= mount_hole_spacing/2 同位）
  - revision `2.0.0 → 2.1.0` ASSUMED default（"升一版"取 minor bump，正式化重建属结构性变更）
- Fastening & mounting: 2×⌀5 安装孔沿 +X 贯穿竖壁（螺栓插入方向 +X，头侧 x=-2 背面），固定于机架 → fixed_support 即竖壁背面；⌀6 承载孔沿 +Z 贯穿横板（吊挂/紧固载荷）
  Envelope math: 安装孔边距：孔心 y=±11 距侧边 |11−2.5|=8.5 ≥ r ✓；距顶 36−22.32=13.68−2.5=11.18 ✓；两孔间净距 22−5=17 ✓；承载孔距横板前端 26−12−3=11、距筋带外缘 y=9.5−3=6.5 ✓（legacy 已验证布局，本次等价重建不改）
- Service conditions: FEM 用例（CalculiX）以 interface.* 为边界条件接口——fixed_support 全约束、load_surface/孔承载（工况由下游 run_calculix.py 定义；本模型不声明强度结论）
- Export targets: `.scadpkg`（必须，路径 out/ap242_gmsh_volume_mesh/ap242_gmsh_bracket.scadpkg 不变）+ STEP（AP242）+ OBJ + STL + FCStd（第 2 轮用户补充）；export_*.py 脚本不改、重跑必须通过
- Verification intent（验收前写定）:
  - V1 新旧体积偏差 < 0.1%（对 legacy_baseline 实测 10097.790499）
  - V2 interface 标签集合完全一致 = {fixed_support, load_surface, mount_hole_1, mount_hole_2, load_hole}，且各标签面面积/质心与 legacy 实测一致（面积相对差 ≤1e-6 量级、质心 ≤1e-5 mm，同 export_fem_mesh 匹配阈值量级）
  - V3 BREP 单实体、闭壳、正体积（外置 inspect）
  - V4 孔位/孔径实测：⌀5×2 @ (y=±11, z=22.32) 轴 X；⌀6 @ (x=12, y=0) 轴 Z；bbox 三向与 legacy 一致（±0.05）
  - V5 scadpkg 新进程重开校验（read+validate）；export_step/export_obj/export_stl 重跑通过
  - V6 视觉：4 视图渲染（iso/front/top/detail 筋+安装孔特写），隔离评审逐区域 match/mismatch/unreviewable
- Ask-or-Record ledger（批量一问，用户已按上稿预答）:
  | item | asked/assumed | answer/value |
  | --- | --- | --- |
  | 几何等价判据 | asked (批量) | 用户预答：体积 <0.1% + 标签集合完全一致（上稿第 2 条） |
  | interface.* 标签处置 | asked (批量) | 用户预答：原样保留，下游 FEM 依赖（上稿第 3 条） |
  | 运行契约 | asked (批量) | 用户预答：包路径/part id 不变、revision 升一版、export_* 不改重跑通过（上稿第 4 条） |
  | 验证方式 | asked (批量) | 用户预答：外置 verify 脚本五项（上稿第 5 条） |
  | rib_offset_y=11 | assumed | legacy 字面量 -11/+11；取 |11|=spacing/2 记为命名参数 |
  | revision 2.1.0 | assumed | minor bump（正式化重建为结构性变更） |
  | rib 轮廓 tier | assumed | geometry tier（FTC 转录条款：坐标已知的既有几何转录，profile=geometry 诚实标注） |
