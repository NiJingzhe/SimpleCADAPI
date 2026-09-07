# Requirements: u_link_motor_mount（参数化 U 形电机连杆）

- Inputs: 用户 prose 描述 + 一轮批量确认（5 问，2026-08-26）
- Functional goals:
  1. 参数化机械臂连杆：长度变化由 `L` 驱动，结构自适应
  2. 通用电机安装：两端圆柱凹槽对电机自定心定位
  3. 安装面具备确定性命名，之后可被 QL 索引（表达"这是安装面"）
- Geometry targets（分区描述，已确认）:
  1. **U 形杆**：圆形截面（⌀`d_profile`）沿「左臂向下 → 底部向右 → 右臂向上」路径扫掠，
     两拐角为中心线圆弧 `R_corner`（> d_profile/2，避免扫掠内退化）；臂端为平面圆端盖（法向沿臂轴）。
     开口朝 +Y；臂轴线位于 x=±L/2；底部圆柱轴线位于 y=0。
  2. **电机安装槽**：两侧臂端用 ⌀(`d_profile` − `thickness`) 圆柱沿臂轴 boolean cut（工具上越过臂端，
     下探至 y = `D_motor`/2）→ 槽深 = D − D_motor/2，槽壁厚 = thickness/2。
     （用户修正：切槽工具为圆柱，非球）
  3. **安装面 = 凹槽底面**：平面、法向 +Y、⌀(d_profile − thickness)、位于 y=D_motor/2、x=±L/2。
     确定性命名 `feature.motor_mount_floor_left` / `feature.motor_mount_floor_right`，QL 可索引。
  4. **背面（原平底）**：切除底管 y < back_y 材料，back_y = r·(2·back_cut_frac−1)，
     默认 frac=0.75 → 平面位于底管高度 75% 处（y=7.5，中心线上移半径一半）。
     作用：安装面到背面距离 = d_motor/2 − back_y = 7.5（通孔路径减半），
     未来垂直通孔可穿出背面。确定性命名 `feature.back_face`，QL 可索引。
     （2026-08-26 用户定向：切平面自中心线 50% 上移至 75% 并命名 back face）
  5. **全局倒角** `fillet_r` 平滑（拓扑允许的全部边缘）。
- Units / coordinate convention: mm；原点 = 底部圆柱轴线中点；+X 沿连杆指向右臂；+Y 向上（开口方向）；+Z 横向；基面 y=0。
- Named parameters (Var):
  - `L = 80`（臂轴跨距 / 底宽）
  - `D = 20`（臂端面高度，自 y=0 量；2026-08-26 用户定向 40→20 取半）
  - `d_profile = 30`（圆杆直径）
  - `thickness = 6`（槽壁余量 → 槽壁厚 3）
  - `D_motor = 30`（电机深度；槽底 y = 15；随 D=20 联动 70→30 保槽深 5）
  - `R_corner = 17`（拐角中心线圆弧半径；随 D=20 联动 20→17，须∈(d_profile/2, D)）ASSUMED
  - `fillet_r = 1.2` ASSUMED default（约束 `fillet_r < thickness/2`）
  - `back_cut_frac = 0.75`（背切平面位置，底管高度百分比；0.5=中心线；2026-08-26 用户定向 0.5→0.75）
  - 约束链（S6/S7 扫描验证后的最终版，全部严格不等式）：
    `D_motor/2 < D`；`d_profile/2 < R_corner < D`；`L > 2·R_corner`；
    `0.5 ≤ back_cut_frac < 1` 且 `back_y < D_motor/2`（背面低于槽底）；
    `fillet_r < thickness/4`（端面环宽 thickness/2 内双侧倒角不得相遇）；
    `fillet_r < (d_profile−thickness)/2`（槽底倒角不得吃穿槽半径）；
    `fillet_r < D−D_motor/2`（槽底倒角不得越过槽口）
- Fastening & mounting: 电机置入 ⌀24 槽内、法兰底面贴安装面；安装面垂直通孔（本轮不建，下轮基于命名安装面添加）。
  Envelope math: 通孔路径 y: D_motor/2 → 0，孔长 = D_motor/2；出口在平底面。
- Service conditions: 未声明（不做强度/FEM 断言）
- Export targets: `.scadpkg` + `STEP` + `STL` → `examples/u_link_motor_mount/out/`
- Verification intent（验收前已写定）:
  - V1 单实体、正体积；未倒角前 bbox = (L+d_profile) × d_profile(Z) × D(Y)（切平底后）
  - V2 平底面存在：平面 y=0
  - V3 安装面恰好 2 个：QL 按命名索引命中，平面法向 +Y，y=D_motor/2，x=±L/2，⌀=d_profile−thickness
  - V4 槽深 = D − D_motor/2（=5），槽壁 = thickness/2（=3）
  - V5 倒角后仍单实体、bbox 不变（容差 ±0.05）、命名安装面仍可被 QL 索引
  - V6 scadpkg 新进程重开校验；STEP/STL 导出成功且文件非空
- Ask-or-Record ledger:
  | item | asked/assumed | answer/value |
  | --- | --- | --- |
  | 安装面定义 | asked | 圆柱凹槽底面（用户修正：圆柱切槽非球；安装面=槽底平面） |
  | 底部切半方式 | asked | 切下半留平底 |
  | 通孔本轮建否 | asked | 暂不建孔 |
  | 单位/默认参数 | asked | mm + 推荐默认（L80/D40/杆⌀30/thickness6/D_motor70） |
  | 导出格式 | asked | scadpkg + STEP + STL |
  | R_corner | assumed | 20（> d_profile/2=15，防扫掠退化；未单独问）；2026-08-26 联动改 17（新约束 ∈(15, D=20)） |
  | fillet_r | assumed | 1.2（< thickness/2=1.5；R1.5 会与壁厚恰好相切退化） |
  | 坐标/原点 | assumed | 原点=底部圆柱轴线中点，X 沿连杆，Y 向上 |
  | D 减半变更 | asked (用户定向) | D 40→20；守卫推导联动 d_motor 70→30（保槽深 5）、R_corner 20→17（新上界 D） |
  | 背切上移+命名 | asked (用户定向) | back_cut_frac 0.5→0.75（中心线上移半径一半=75% 高度）；切出平面命名 feature.back_face；联动新守卫 0.5≤frac<1、back_y<d_motor/2 |

## S8 变更（2026-08-26）：背腔 + 卡扣 + 盖子 + 装配

- 功能: 电机螺丝孔与线束藏于背腔,盖子卡扣封盖;交付完整装配（用户选定）。
- 几何发现（verify/s8_preprobe.py 实测本体）:
  back face 上方材料厚度: 直段中央 7.5 / 直段侧边 z=11 仅 2.7 / z=12.5 仅 0.79 / 两端（x∈28~51, z≤9）12.5。
  → **均匀内缩轮廓被证伪**（内缩 wall 后膜≈0.58·wall, wall=2 时减倒角后深度≈0）;孔位（x≈±40±pc）恰在厚区。
- 设计（用户确认: 哑铃+腰×4 卡扣+3mm+1.2mm+pc=8 校验+完整装配）:
  1. **背腔（哑铃）**: 2D union(腰矩形 x∈±28 z±5.5, 两腔矩形 x∈±[28,47.5] z±7.5) 拉伸 cut,深 3 → 槽底 y=10.5;
     安装面下壁 = 15−10.5 = 4.5（螺丝穿孔路径）;腰膜 3.46−fillet1.2 = 2.26;腔壁到 back face 边 ≥1.36。
  2. **卡扣孔**: 4×Ø2.5 盲孔,轴 Z,孔心 (±12, 8.9),z∈[5.5,9.5]（开口于腰侧壁;z=9.5 处壁 y_top=11.46>孔上缘 10.15 余 1.31,不露外）。
  3. **盖子**: 哑铃轮廓内缩 0.15,板厚 1.2（y∈[7.5,8.7],外底面与 back face 平齐）;4 悬臂梁（1.6×0.7,z 5.05→9.3）+
     爪（y 8.7→10.35,卡量 0.2 于孔上缘 10.15）;不倒角（薄壁件）。建模在安装位,装配 placement=identity。
  4. **装配**: 本体 ground + cover fixed（back-face ↔ cover-bottom connector）;@assemble definitions 两 part。
- 新参数（Var）: waist_z=5.5, pocket_z=7.5, waist_x=28, pocket_x2=47.5, cavity_h=3.0,
  snap_hole_d=2.5, snap_x=12, snap_hole_y=8.9, snap_hole_len=4.0, cover_t=1.2, cover_clr=0.15, motor_pc=8.0
- 守卫新增: 腰/腔轮廓 ⊆ {膜≥fillet_r+1.0}（用解析网格采样校验）;孔域 ⊆ 壁内（不露外）;
  cavity_h < back壁厚 −(安装面下壁≥2) → back_y+cavity_h ≤ d_motor/2−2;motor_pc 孔位 ⊆ 腔轮廓（覆盖校验）
- S8 验证意图: 槽底/轮廓/4 孔几何;命名面(back/mount)仍可索引;盖板/钩几何;配合干涉=0;
  螺丝孔位(pc=8)⊂腔;装配 solve+capture 重开

## S9 变更（2026-08-26）：弃卡扣 → boss 柱 + 盖子孔（用户定向"简单一点"）

- 撤销: S8 卡扣孔/盖爪方案（含 snap_* 参数与工具）。
- 新方案: 背腔内 4 根 boss 柱 + 盖子 4 孔, 螺丝穿盖拧入 boss 压紧盖子。
- 布局（ASSUMED, 字面"上下左右"落到哑铃腔）: 两端腔各 2 根, 上下布置, 左右对称——
  boss 轴 (±boss_x, cavity 底面), boss_x=39, boss_z=±3.5;
  避让校验: boss 到 pc=8 电机孔位最小距离 = sqrt(4.66²+2.16²)=5.14 ≥ boss_r+hole_r+1.0=5.0 ✓。
- boss 几何: 柱 Ø5.0, y∈[back_y, back_y+cavity_h]（贯穿腔, 顶端与背面平齐）;
  中心自攻孔 Ø2.7 深 2.5（留底 0.5）; 顶端外缘 chamfer 0.5（盖孔套入引导）;
  根部参与全局 fillet R1.2（加强）。
- 加强筋: 每 boss 1 片 x 向筋板, 长 2*(boss_r+2.5)=10, 厚 1.2, 高 1.5（y∈[cavity 底-1.5, 底]）,
  筋顶与盖子内面留 0.3; 筋不参与倒角（壁厚 1.2 < 2×R1.2, 圆角相遇会吃穿——工程上正确）。
- 盖子: 哑铃轮廓外边界内缩 cover_clr=0.15（腰/腔过渡面为内部面不缩, 腰板延伸 0.15 与腔板重叠
  保 union 连续）; 板厚 1.2, 外底面与 back face 平齐; 4×Ø5.5 通孔对准 boss（间隙 0.5）;
  薄壁不倒角。
- 装配: body ground + cover fixed（back-face ↔ cover-bottom placement connector, 同坐标系零残差）;
  @assemble definitions=[body, cover], capture 装配包。
- 新参数（Var）: boss_d=5.0, boss_hole_d=2.7, boss_hole_depth=2.5, boss_x=39.0, boss_z=3.5,
  rib_t=1.2, rib_h=1.5, rib_len=2.5, boss_chamfer=0.5, cover_hole_d=5.5
- 移除参数: snap_hole_d/snap_x/snap_hole_y/snap_hole_len
- 守卫更新: boss+筋 ⊆ 腔轮廓（端腔 x∈[waist_x,pocket_x2] z∈±pocket_z 内缩 0.5）;
  dist(boss, 电机孔位) ≥ boss_r+hole_r+1.0（避让, pc=motor_pc=8 假设轮保留为校验参数）;
  boss_hole_depth ≤ cavity_h-0.5; 筋顶 ≤ 盖子内面-0.2
- S9 验证意图: 4 boss 存在（QL 柱面+解析体积）; 4 盲孔; 筋体积; boss 避让解析;
  盖子轮廓⊂腔+0.15 缝、孔位对齐 boss、厚 1.2; 装配 solve 零残差+重开; 命名面回归

## S10 变更（2026-08-26）：弃方形腔 → 75% 剖分成两件 + 轮廓贴合 shell（用户定向）

- 撤销: S8/S9 方形哑铃腔、背部 boss、盖板 cover.py。
- 核心: 腔体由"管形内偏移 wall_t 的扫掠体"构成——**精确贴合背板轮廓**（圆截面沿同路径
  半径 r−wall_t 扫掠 = 解析内偏移；直段+圆弧段均精确），非手工矩形。
- 剖分（两次 cut，各保留一半）:
  * 上件 blank: cut @ y=back_y−boss_h（75% 点下移 boss 高）, 去
    下半 → 材料.extend 到 y=7.5−boss_h;
  * 下件: cut @ y=back_y(7.5), 保下半 → 底段槽 [−15, 7.5]。
- 上件终态: band [7.5−boss_h, 7.5] 用内偏移扫掠腔 hollow（工具带 boss 圆孔→
  留 integral boss 残柱）; boss Ø5×boss_h 垂于切面中央 (±boss_x, z=0), 中心盲孔
  Ø2.7 自柱底向上; 4 方向三角筋（垂直边贴柱 boss_h 高, 水平边沿 7.5 天花板
  rib_len, 厚 rib_t）+ 筋倒角; 全局倒角(排除 boss/筋区+切面外缘切线边)。
- 下件 shell: 下段 − 内偏移扫掠(y≤7.5) → 壁厚 wall_t 的外壳（开口向上 7.5）;
  两端外壁走线方口（4×4, 过壁, 近臂端外侧）; 底板对 boss 位通孔 Ø=boss_hole_d
  （用户明确: 孔内径与 boss 内径一致, 自攻贯穿拧入）。
- 装配: 上件 ground + shell fixed @ 7.5 环形接口; 上件 back face tag 移至剖分环面。
- 新参数: wall_t=2.0(ASSUMED), boss_h=5.0(ASSUMED), boss_x=12.0(切面中央, ASSUMED),
  rib_len=3.0, gusset_chamfer=0.3, notch=4×4(ASSUMED 位置近臂端外壁)
- 移除参数: waist_z/pocket_z/waist_x/pocket_x2/cavity_h/boss_z/rib_h/rib_t 旧义/
  boss_chamfer/cover_*
- 守卫: wall_t < r−安全; boss_h < back_y−2; boss 区 ⊆ 内偏移开口(z 半宽
  sqrt((r−wall_t)²−back_y²)−0.5); boss 避让电机孔位(沿用户必须的假设保持)
- S10 验证意图: 内偏移腔体积=Pappus(r−wall_t 段); 上件 bbox y=[7.5,D]; boss
  柱/盲孔/8 三角筋几何; 筋倒角落地; 命名面(mount×2+back 环); shell 壁厚采样
  ≥wall_t−0.1、走线口贯穿、底孔位/boss 对齐 Ø 一致; 装配零残差; 干涉=0

## S11 变更（2026-08-26）：两刀工艺修正 + 沉头孔 + 大走线口 + 深槽（用户定向）

- 修正 S10 结构缺陷: shell 螺栓孔原打在管底(−15)距 boss 尖 15.5mm 螺栓悬空。
- 二次修正（用户指出底面错误）: shell 底面必须是**第一刀平面(0.5)**，非原始管底曲面。
  正确顺序: 第一刀@0.5 切掉下半部（产生平底）→ 第二刀@7.5 分离两件。
- shell = rod ∩ [0.5, 7.5] − 内偏移扫掠∩[2.5, 7.5]:
  **平底面 0.5**(整弦截面 2738mm², feature.shell_hole_floor) + 实体地板 [0.5,2.5]
  (顶面 2.5 恰贴 boss 尖端) + 轮廓壁 wall_t 腔体 [2.5,7.5](容 boss+线束);
  地板沉头孔(Ø2.7 通 + 90° 锥口 Ø5.4×1.35 **自平底向上**);
  两端 **9×5 腔高走线方口**(x≈±44.75, 贯穿端壁, 原 4×4 加大)。
- 深槽: d_motor 30→19(槽深 5→10.5), 安装面(9.5)到 back face(7.5)=2.0=标准壁厚
  (新守卫: d_motor/2 ≥ back_y+wall_t)。
- 新参数: notch_w=9, notch_h=7, csink_d=5.4, csink_depth=1.35
- S11 验证意图: 接触面 floor_top==boss_tip(2.5); 地板实体+上下腔空; 锥面×2+通孔壁;
  方口贯通; 零干涉(采样避开接触面); 槽壁厚=wall_t 精确; 全回归含 sweep(12 变体+14 边界)

## S12 变更（2026-08-26）：防割手圆角（用户定向）

- 需求: shell 平底(第一刀面)外缘 + 走线口边缘全部圆角，防割手。
- 实现:
  1. 平底外缘: fillet R=safe_fillet_r(0.6)——外环 wire 选中（直段圆柱面+拐角 torus 环带），一次成功
  2. 走线口: **rounded-rect 轮廓源型**（角 R=notch_rr=1.5 圆角融入 wire-extrude 工具，
     上下各留 sill=0.5 台阶避共面）——矩形口边缘 fillet 在口角三面圆角相遇处
     内核稳定崩溃(R0.3~0.6 全败, 单边全过组合必崩, s12 逐边取证), 源型圆角是
     唯一稳定方案且更符合注塑工艺
- 新参数: notch_sill=0.5, notch_rr=1.5, safe_fillet_r=0.6
- S12 验证意图: C1 rim 圆角面(torus≥4+rim_cyl≥2); C2 口角圆柱面≥6; C3 上下 sill
  材料完好+口敞开; C4 沉头/地板/平底回归

## S13 变更（2026-08-26）：电机槽走线窗（用户定向）

- 需求: 两电机安装槽侧壁各开 4 窗（相位差 90°）走电源/控制线，适配不同电机出线布局；
  窗底边距安装面 ≥3mm 且 ≤5mm（推荐 3，用户规定）。
- 实现（用户定向：切口在链**最后一步**做——倒角后成品拓扑上直接切出）:
  rounded-rect 棱柱（5×5, 角 R1.2 圆角防割手）×2 条过轴工具旋转 ±45°，
  每槽对角 4 窗共 8 窗；相位 45° 由方向开度探针决定（s13-P1: 0/180° 内向在
  y=13/15 撞拐角熔合区盲, 对角四向全开）。
- 新参数: cable_w_off=3, cable_w_h=5, cable_w_w=10（S14 用户定向 5→10 周向 2 倍）, cable_w_rr=1.2, cable_w_phase=45
- S14（2026-08-26）: 周向加宽 2 倍。守卫上界随之 1.2→1.6×槽半径（w=10/rp=12 时窗间弧余 34mm 充裕）；
  体积公式实测系数 0.85→1.046（弧壁外表面弧长>内表面，宽窗实测标定）
- 守卫: 3≤cable_w_off≤5（用户规定）; 窗顶 ≤ D-2; rr<半宽/半高; 窗宽 ≤1.2×槽半径
- 深槽联动发现: D=26/dm=44 变体臂端余量 4mm < off+h —— 与窗需求本质冲突,
  变体联动 dm→36（守卫给出可行域 dm ≤ 2(D-2-off-h)）
- S13 验证意图: P1 方向开度图; P2 8 窗全开+窗间壁完好+底边恰 3mm（±0.3 采样）
