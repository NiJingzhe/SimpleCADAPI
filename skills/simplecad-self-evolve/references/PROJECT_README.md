# SimpleCADAPI

SimpleCADAPI 是一个基于 CADQuery 的命令式 CAD 建模 Python 包，目标是把常见建模动作封装成清晰、可组合、可测试的函数式 API，并支持通过 Skills 方式分发“文档 + 脚本 + 运行时安装”工作流。

## README 定位

本 README 仅包含包级能力、安装方式、发布/打包流程与 Skills 使用说明。
实验性脚本和临时建模样例不作为正式文档内容。

## 包安装（Python 包管理器）

当前包名：`simplecadapi`，版本：`2.0.3`（见 `pyproject.toml`）。

### 方式 A：用 pip 从包仓库安装

```bash
pip install simplecadapi
```

开发依赖可选安装：

```bash
pip install "simplecadapi[dev]"
```

### 方式 B：用 uv 安装

在当前虚拟环境安装：

```bash
uv pip install simplecadapi
```

作为项目依赖写入 `pyproject.toml`：

```bash
uv add simplecadapi
```

### 方式 C：从本地构建产物安装

仓库内已有示例构建产物（`dist/`）：

```bash
pip install dist/simplecadapi-2.0.3-py3-none-any.whl
```

如果你需要重新构建：

```bash
uv build
```

## 快速验证安装

```python
import simplecadapi as scad

box = scad.make_box_rsolid(10.0, 20.0, 30.0)
scad.export_stl(box, "example_box.stl")
scad.export_step(box, "example_box.step")
```

## 如何打包并使用 Skills

本项目提供 `skill-pack` CLI，用于生成轻量技能包（thin mode）：**不内置 SDK 源码**，运行时从包仓库安装 `simplecadapi`。

### 1) 打包命令

在仓库根目录执行：

```bash
uv run skill-pack --refresh-docs --archive --skill-name simplecad-self-evolve
```

常用参数：

- `--output-root <dir>`：输出目录（默认 `./skills`）
- `--package-name <pkg>`：运行时安装包名（默认读取 `project.name`）
- `--package-version <ver>`：运行时安装版本（默认读取 `project.version`）
- `--no-clean`：不清理已有输出目录
- `--archive`：额外生成 `<skill-name>.tar.gz`

### 2) 打包结果结构

打包后将得到类似目录：

- `skills/simplecad-self-evolve/SKILL.md`
- `skills/simplecad-self-evolve/scripts/`
- `skills/simplecad-self-evolve/references/`
- `skills/simplecad-self-evolve/cases/simplecad_self_evolve_cases/`

### 3) 在 skill 目录中安装并检查运行时

```bash
cd skills/simplecad-self-evolve
PYTHON_BIN=.venv/bin/python scripts/install.sh
PYTHON_BIN=.venv/bin/python scripts/with_skill.sh --check
```

### 4) 用包装脚本运行你的程序

```bash
PYTHON_BIN=.venv/bin/python scripts/with_skill.sh -- .venv/bin/python your_script.py
```

### 5) 激活 skill-local 案例模块路径

```bash
eval "$(scripts/with_skill.sh --print-env)"
```

激活后可直接导入：

```python
from simplecad_self_evolve_cases.evolve import make_involute_spur_gear_rsolid
```

### 6) 向 skill 本地 evolve 模块追加新函数

```bash
scripts/add_new_case.sh path/to/new_case.py
```

### 7) Jupyter 与结构校验

```bash
scripts/jupyter_with_skill.sh lab
scripts/validate_skill.sh
```

## 自动化工具（Auto Tools）

项目内置 4 个主要 CLI：

- `auto-docs-gen`：从 API 源码生成 `docs/api/` 文档
- `make-export`：更新 `src/simplecadapi/__init__.py` 的导入导出
- `evolve`：从脚本提取函数并追加到 evolve 模块
- `skill-pack`：打包 thin skill（文档 + 脚本 + cases）

示例：

```bash
uv run make-export --dry-run
uv run auto-docs-gen
uv run evolve path/to/your_case.py
uv run skill-pack --refresh-docs --archive
```

## RAGFlow 文档同步

`scripts/sync_ragflow_docs.py` 用于把 `docs/` 下的 Markdown 增量同步到指定
RAGFlow 数据集，并按二级标题（H2）分块；文档的 `chunk_method` 会设置为
`manual`。

准备环境：

```bash
.venv/bin/python -m pip install ragflow-sdk
```

建议使用 `.env`（已加入 `.gitignore`）：

```bash
RAGFLOW_API_KEY=your_key_here
RAGFLOW_BASE_URL=http://localhost
RAGFLOW_DATASET_NAME=SimpleCADAPI
```

运行同步：

```bash
set -a && source .env && set +a
.venv/bin/python scripts/sync_ragflow_docs.py --create-dataset
```

常用参数：

- `--dataset-id` / `RAGFLOW_DATASET_ID`：直接指定数据集 ID（避免同名冲突）
- `--delete-removed`：同步删除本地已移除的文档
- `--dry-run`：只预览变更，不执行写入
- `--progress-interval N`：每 N 篇打印一次进度

## 开发与测试

本地开发安装（可编辑）：

```bash
uv pip install -e ".[dev]"
```

运行单元测试：

```bash
uv run python -m unittest test/test_all_features.py
```

运行示例：

```bash
uv run python examples.py
```

## 核心设计约束（简要）

- API 函数统一使用 `snake_case`，并通过函数名体现返回类型（如 `*_rsolid`、`*_rwire`）。
- 核心类型尽量稳定，功能扩展通过新增函数完成（开放封闭原则）。
- 支持 `SimpleWorkplane` 上下文进行局部坐标建模。
- 导出接口支持单实体、多实体及嵌套列表输入。

## 文档入口

- API 文档：`docs/api/`
- Core 文档：`docs/core/`

## License

MIT，见 `LICENSE`。
