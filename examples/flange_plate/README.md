# 六孔法兰盘（FTC 单零件示例）

最简 Feature Tree Convention 示例：一个 `@scad.part` 单零件，纯几何体素
（geometry tier 第 3 类：形状完全含于基本体素），QL 选边做圆角，外置脚本验证。

## 形状 brief（尺寸为演示假设值，mm）

| 特征 | 参数 | 值 |
| --- | --- | --- |
| 法兰盘 | 外径 × 厚 | Ø100 × 10（z 0..10） |
| 中心凸台 | 外径 × 顶高 | Ø55，顶面 z=30 |
| 中心孔 | 通孔直径 | Ø30 |
| 螺栓孔 | 数量 × 孔径 × 分布圆 | 6 × Ø11 × PCD Ø78 |
| 圆角 | 凸台根部 R3；盘外缘上下 R2 | |

基准：原点在盘底中心，+Z 为盘厚方向。可行性链（参数守卫在源码内）：
孔边到外缘轮辐 50−39−5.5=5.5 ≥ R2；孔边到根部圆角 39−5.5=33.5 ≥ 27.5+3。

## 特征树

```text
flange-disc (build) -> hub-boss (add) -> center-bore (subtract)
-> bolt-holes (subtract) -> hub-root-fillet (modify) -> rim-fillet (modify)
```

## 运行

```bash
uv run python examples/flange_plate/model.py    # 建模 + scadpkg/step/PNG
uv run python examples/flange_plate/verify.py   # 外置验证（断言，非目检）
```

产物写入 `examples/out/flange_plate/`。

## 验证契约（verify.py）

- 单实体、体积与解析值偏差 < 1%；
- QL：Ø11 圆孔圆缘边 12 条（6 孔 × 上下），孔心距轴 = PCD/2；
- 中心孔 Ø30（圆缘周长 2π·15）上下各一条；
- 圆角面 TORUS 恰 3 张（根部 1 + 外缘 2）；
- `.scadpkg` 回读校验、`.step` 非空。
