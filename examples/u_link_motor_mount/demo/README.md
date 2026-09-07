# 会话回放 Demo（单文件离线）

**打开方式：直接双击 `index.html`**（单文件、离线可用、无需服务器；数据、three.js、STL、渲染图全部内联，约 6.3 MB）。

## 这是什么

把 `../session_transcript.md`（2 MB / 590 条消息的真实 OpenCode 会话）**忠实回放**成可交互的演示页面，展示"人如何用自然语言与 Agent 协作完成参数化 CAD 建模"：

- 左侧：逐条回放全部消息——15 轮用户输入（打字机效果）、Agent 思考/回复、601 次工具调用的输入与输出、232 个补丁、22 次角色切换（需求确认 → 总体规划 → 分阶段建模/验证）
- 右侧：three.js 实时渲染会话最终导出的 `out/u_link_assembly.stl`（可旋转/缩放/平移/线框），另有渲染图、终版参数表、导出产物三个面板

## 操作

| 操作 | 方式 |
| --- | --- |
| 播放 / 暂停 | `空格` 或 ▶ 按钮 |
| 跳到下一轮用户输入 | `⇧→` 或 ⏭ 按钮 |
| 直达某一轮 | 点击进度条上的橙色刻度 |
| 全量阅读 | 顶栏「阅读模式」 |
| 倍速 | ×0.5 – ∞ |

## 重新生成

transcript 或产物更新后（在仓库根目录执行）：

```bash
python3 examples/u_link_motor_mount/demo/build.py
```

构建器与前端源码统一在 [`examples/demo_kit/`](../../demo_kit/)（`build_demo.py` +
`template.html` + `app.js` + `app.css` + `vendor/three.js` r147 UMD）；每个 case
的 `demo/build.py` 提供该 case 的文案与素材路径配置，转录格式见
[`examples/demo_kit/TRANSCRIPT_FORMAT.md`](../../demo_kit/TRANSCRIPT_FORMAT.md)。
