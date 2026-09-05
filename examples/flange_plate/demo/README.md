# 会话回放 Demo（单文件离线）

**打开方式：直接双击 `index.html`**（离线可用、无需服务器；数据、three.js、STL、渲染图全部内联，约 1.7 MB）。

把 `../session_transcript.md`（参数化法兰盘：几何体素路线与守卫驱动的改参交付）
**忠实回放**成可交互页面：2 轮用户输入、66 次工具调用、28 个补丁、10 次角色切换
（需求确认 → 总体规划 → S1–S3 分阶段建模/验证 → 导出），右侧 three.js 实时渲染
最终 8 孔法兰盘。看点是第 2 轮改参：PCD 88 被守卫当场拒绝，85 因圆角相切被排除，
84.5 实证可行交付。

## 重新生成（仓库根目录）

```bash
python3 examples/flange_plate/demo/build.py
```

构建器与转录格式见 [`examples/demo_kit/`](../../demo_kit/)。
