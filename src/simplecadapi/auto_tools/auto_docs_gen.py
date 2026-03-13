#!/usr/bin/env python3
"""Generate markdown API docs from source files.

The generator extracts top-level public functions from source files,
parses their docstrings, and writes API markdown pages plus an index page.
"""

from __future__ import annotations

import argparse
import ast
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SOURCES: tuple[Path, ...] = (
    PROJECT_ROOT / "src/simplecadapi/operations.py",
    PROJECT_ROOT / "src/simplecadapi/evolve.py",
    PROJECT_ROOT / "src/simplecadapi/constraints.py",
    PROJECT_ROOT / "src/simplecadapi/ql.py",
)
DEFAULT_OUTPUT_DIRS: tuple[Path, ...] = (PROJECT_ROOT / "docs/api",)

MISSING = object()


@dataclass
class ApiInfo:
    """Container for extracted API metadata."""

    name: str
    signature: str
    source_file: str
    parsed_doc: Dict[str, object]


class APIDocumentGenerator:
    """Generate markdown docs for API functions."""

    def __init__(
        self,
        source_files: Sequence[Path],
        output_dirs: Sequence[Path],
        clean_stale: bool = True,
        quiet: bool = False,
    ):
        self.source_files = list(source_files)
        self.output_dirs = list(output_dirs)
        self.clean_stale = clean_stale
        self.quiet = quiet
        self.apis: List[ApiInfo] = []

    def log(self, message: str) -> None:
        if not self.quiet:
            print(message)

    def extract_apis(self) -> List[ApiInfo]:
        """Extract all top-level public functions with docstrings."""
        self.log("正在分析源文件...")

        extracted: List[ApiInfo] = []
        for file_path in self.source_files:
            if not file_path.exists():
                self.log(f"警告: 找不到文件 {file_path}，跳过。")
                continue

            self.log(f"  正在处理 {file_path}...")
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(file_path))

            file_count = 0
            for node in tree.body:
                if not isinstance(node, ast.FunctionDef):
                    continue
                if node.name.startswith("_"):
                    continue

                docstring = ast.get_docstring(node)
                if not docstring:
                    continue

                extracted.append(
                    ApiInfo(
                        name=node.name,
                        signature=self._get_function_signature(node),
                        source_file=file_path.name,
                        parsed_doc=self._parse_docstring(docstring),
                    )
                )
                file_count += 1

            self.log(f"    从 {file_path.name} 提取到 {file_count} 个API")

        self.apis = extracted
        self.log(f"成功总共提取到 {len(extracted)} 个API")
        return extracted

    def generate_markdown_docs(self) -> None:
        """Generate markdown docs for all configured output directories."""
        if not self.apis:
            self.log("没有可生成的API文档。")
            return

        for output_dir in self.output_dirs:
            self._generate_for_single_output_dir(output_dir)

    def _generate_for_single_output_dir(self, output_dir: Path) -> None:
        output_dir.mkdir(parents=True, exist_ok=True)
        self.log(f"正在生成markdown文档到: {output_dir}")

        generated_files = set()
        created_or_updated = 0

        for api in sorted(self.apis, key=lambda item: item.name):
            filename = f"{api.name}.md"
            file_path = output_dir / filename
            md_content = self._build_single_api_markdown(api)
            changed = self._write_if_changed(file_path, md_content)
            if changed:
                created_or_updated += 1
            generated_files.add(filename)

        readme_path = output_dir / "README.md"
        readme_content = self._build_api_index_markdown()
        if self._write_if_changed(readme_path, readme_content):
            created_or_updated += 1

        removed_count = 0
        if self.clean_stale:
            removed_count = self._remove_stale_docs(output_dir, generated_files)

        self.log(
            f"文档生成完成: {output_dir} "
            f"(更新 {created_or_updated} 个文件, 删除 {removed_count} 个过期文档)"
        )

    def _build_single_api_markdown(self, api: ApiInfo) -> str:
        parsed = api.parsed_doc
        md_lines: List[str] = []

        md_lines.append(f"# {api.name}")
        md_lines.append("")

        md_lines.append("## API Definition")
        md_lines.append("")
        md_lines.append("```python")
        md_lines.append(api.signature)
        md_lines.append("```")
        md_lines.append("")
        md_lines.append(f"*Source: {api.source_file}*")
        md_lines.append("")

        description = str(parsed.get("description", "")).strip()
        usage = str(parsed.get("usage", "")).strip()
        usage_parts = [part for part in [description, usage] if part]
        if usage_parts:
            merged_usage = "\n\n".join(dict.fromkeys(usage_parts))
            md_lines.append("## Description")
            md_lines.append("")
            md_lines.extend(merged_usage.splitlines())
            md_lines.append("")

        args = parsed.get("args", [])
        if isinstance(args, list) and args:
            md_lines.append("## Parameters")
            md_lines.append("")
            for arg in args:
                arg_name = str(arg.get("name", "")).strip()
                arg_type = str(arg.get("type", "")).strip()
                arg_desc = str(arg.get("description", "")).strip()

                md_lines.append(f"### {arg_name}")
                md_lines.append("")
                if arg_type:
                    md_lines.append(f"- **Type**: `{arg_type}`")
                md_lines.append(f"- **Description**: {arg_desc}")
                md_lines.append("")

        returns_text = str(parsed.get("returns", "")).strip()
        if returns_text:
            md_lines.append("## Returns")
            md_lines.append("")
            md_lines.extend(returns_text.splitlines())
            md_lines.append("")

        raises = parsed.get("raises", [])
        if isinstance(raises, list) and raises:
            md_lines.append("## Raises")
            md_lines.append("")
            for exc in raises:
                exc_type = str(exc.get("type", "")).strip()
                exc_desc = str(exc.get("description", "")).strip()
                md_lines.append(f"- **{exc_type}**: {exc_desc}")
            md_lines.append("")

        examples = parsed.get("examples", [])
        if isinstance(examples, list) and examples:
            md_lines.append("## Examples")
            md_lines.append("")
            for index, block in enumerate(examples, start=1):
                if len(examples) > 1:
                    md_lines.append(f"### Example {index}")
                md_lines.append("```python")
                md_lines.extend(block.splitlines())
                md_lines.append("```")
                md_lines.append("")

        return "\n".join(md_lines).rstrip() + "\n"

    def _build_api_index_markdown(self) -> str:
        categories: Dict[str, List[ApiInfo]] = {
            "Basic Creation": [],
            "Transforms": [],
            "3D Operations": [],
            "Tagging and Selection": [],
            "Boolean Operations": [],
            "Export": [],
            "Advanced Features": [],
            "Evolve": [],
            "Assembly Constraints": [],
            "Other": [],
        }

        for api in self.apis:
            name = api.name

            if api.source_file == "evolve.py":
                categories["Evolve"].append(api)
                continue

            if api.source_file == "constraints.py":
                categories["Assembly Constraints"].append(api)
                continue

            if name.startswith("make_"):
                categories["Basic Creation"].append(api)
            elif name.startswith(("translate_", "rotate_", "mirror_")):
                categories["Transforms"].append(api)
            elif name.startswith(("extrude_", "revolve_", "loft_", "sweep_")):
                categories["3D Operations"].append(api)
            elif name.startswith(("set_tag", "select_")):
                categories["Tagging and Selection"].append(api)
            elif name.startswith(("union_", "cut_", "intersect_")):
                categories["Boolean Operations"].append(api)
            elif name.startswith("export_"):
                categories["Export"].append(api)
            elif name.startswith(
                ("fillet_", "chamfer_", "shell_", "pattern_", "helical_")
            ):
                categories["Advanced Features"].append(api)
            else:
                categories["Other"].append(api)

        md_lines: List[str] = [
            "# SimpleCAD API Index",
            "",
            "This index includes API docs generated from `operations.py`, `evolve.py`, `constraints.py`, and `ql.py`.",
            "",
        ]

        for category, api_list in categories.items():
            if not api_list:
                continue
            md_lines.append(f"## {category}")
            md_lines.append("")
            for api in sorted(api_list, key=lambda item: item.name):
                source_info = f" *(来自 {api.source_file})*"
                md_lines.append(f"- [{api.name}]({api.name}.md){source_info}")
            md_lines.append("")

        return "\n".join(md_lines).rstrip() + "\n"

    def _remove_stale_docs(self, output_dir: Path, generated_files: set[str]) -> int:
        removed = 0
        keep = set(generated_files)
        keep.add("README.md")

        for path in output_dir.glob("*.md"):
            if path.name in keep:
                continue
            path.unlink()
            removed += 1

        return removed

    @staticmethod
    def _write_if_changed(file_path: Path, content: str) -> bool:
        if file_path.exists() and file_path.read_text(encoding="utf-8") == content:
            return False
        file_path.write_text(content, encoding="utf-8")
        return True

    def _parse_docstring(self, docstring: str) -> Dict[str, object]:
        sections = {
            "description": [],
            "args": [],
            "returns": [],
            "raises": [],
            "usage": [],
            "examples": [],
        }

        current_section = "description"
        for raw_line in docstring.splitlines():
            stripped = raw_line.strip()

            next_section = self._map_section_header(stripped)
            if next_section:
                current_section = next_section
                continue

            sections[current_section].append(raw_line.rstrip())

        parsed: Dict[str, object] = {
            "description": self._collapse_paragraph_lines(sections["description"]),
            "args": self._parse_args_section(sections["args"]),
            "returns": self._collapse_paragraph_lines(sections["returns"]),
            "raises": self._parse_raises_section(sections["raises"]),
            "usage": self._collapse_paragraph_lines(sections["usage"]),
            "examples": self._parse_examples_section(sections["examples"]),
        }
        return parsed

    @staticmethod
    def _map_section_header(stripped_line: str) -> str | None:
        normalized = stripped_line.rstrip(":").strip().lower()
        if normalized in {"args", "argument", "arguments", "parameters", "params"}:
            return "args"
        if normalized in {"returns", "return"}:
            return "returns"
        if normalized in {"raises", "raise", "exceptions", "exception"}:
            return "raises"
        if normalized in {"usage", "how to use"}:
            return "usage"
        if normalized in {"example", "examples"}:
            return "examples"
        return None

    @staticmethod
    def _collapse_paragraph_lines(lines: Iterable[str]) -> str:
        filtered: List[str] = []
        previous_blank = False
        for line in lines:
            text = line.strip()
            if not text:
                if not previous_blank:
                    filtered.append("")
                previous_blank = True
                continue
            filtered.append(text)
            previous_blank = False
        return "\n".join(filtered).strip()

    def _parse_args_section(self, lines: Iterable[str]) -> List[Dict[str, str]]:
        args: List[Dict[str, str]] = []
        current: Dict[str, str] | None = None

        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                continue

            if ":" in stripped and not stripped.startswith(("-", "* ")):
                if current:
                    args.append(current)

                left, right = stripped.split(":", 1)
                left = left.strip()
                description = right.strip()

                if not left:
                    if current:
                        current["description"] = (
                            f"{current['description']} {stripped}".strip()
                        )
                    continue

                name = left
                type_info = ""
                if "(" in left and ")" in left and left.endswith(")"):
                    open_index = left.rfind("(")
                    close_index = left.rfind(")")
                    if open_index < close_index:
                        name = left[:open_index].strip()
                        type_info = left[open_index + 1 : close_index].strip()

                current = {"name": name, "type": type_info, "description": description}
                continue

            if current:
                current["description"] = f"{current['description']} {stripped}".strip()

        if current:
            args.append(current)

        return args

    def _parse_raises_section(self, lines: Iterable[str]) -> List[Dict[str, str]]:
        raises: List[Dict[str, str]] = []
        current: Dict[str, str] | None = None

        for raw_line in lines:
            stripped = raw_line.strip()
            if not stripped:
                continue

            if ":" in stripped and not stripped.startswith(("-", "* ")):
                if current:
                    raises.append(current)
                exc_name, exc_desc = stripped.split(":", 1)
                current = {"type": exc_name.strip(), "description": exc_desc.strip()}
                continue

            if current:
                current["description"] = f"{current['description']} {stripped}".strip()

        if current:
            raises.append(current)

        return raises

    @staticmethod
    def _parse_examples_section(lines: Iterable[str]) -> List[str]:
        blocks: List[str] = []
        current: List[str] = []

        for raw_line in lines:
            if raw_line.strip() == "":
                if current:
                    blocks.append(
                        APIDocumentGenerator._normalize_example_block(current)
                    )
                    current = []
                continue
            current.append(raw_line)

        if current:
            blocks.append(APIDocumentGenerator._normalize_example_block(current))

        return [block for block in blocks if block.strip()]

    @staticmethod
    def _normalize_example_block(lines: List[str]) -> str:
        while lines and not lines[0].strip():
            lines = lines[1:]
        while lines and not lines[-1].strip():
            lines = lines[:-1]
        if not lines:
            return ""
        return textwrap.dedent("\n".join(lines)).strip("\n")

    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        params: List[str] = []

        positional = list(node.args.posonlyargs) + list(node.args.args)
        padded_defaults = [MISSING] * (
            len(positional) - len(node.args.defaults)
        ) + list(node.args.defaults)

        for arg, default in zip(positional, padded_defaults):
            params.append(self._format_arg(arg, default))

        if node.args.posonlyargs:
            params.insert(len(node.args.posonlyargs), "/")

        if node.args.vararg:
            params.append(f"*{self._format_arg(node.args.vararg)}")
        elif node.args.kwonlyargs:
            params.append("*")

        for kw_arg, kw_default in zip(node.args.kwonlyargs, node.args.kw_defaults):
            default = kw_default if kw_default is not None else MISSING
            params.append(self._format_arg(kw_arg, default))

        if node.args.kwarg:
            params.append(f"**{self._format_arg(node.args.kwarg)}")

        returns = ""
        if node.returns is not None:
            returns = f" -> {self._safe_unparse(node.returns)}"

        return f"def {node.name}({', '.join(params)}){returns}"

    def _format_arg(self, arg: ast.arg, default: object = MISSING) -> str:
        text = arg.arg
        if arg.annotation is not None:
            text += f": {self._safe_unparse(arg.annotation)}"
        if default is not MISSING:
            text += f" = {self._safe_unparse(default)}"
        return text

    @staticmethod
    def _safe_unparse(node: ast.AST | object) -> str:
        if not isinstance(node, ast.AST):
            return "..."
        try:
            return ast.unparse(node)
        except Exception:
            return "..."


def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="SimpleCAD API markdown docs generator"
    )
    parser.add_argument(
        "--source",
        dest="sources",
        action="append",
        help="Source file path. Can be provided multiple times.",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dirs",
        action="append",
        help="Output directory path. Can be provided multiple times.",
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Keep stale markdown API docs instead of deleting them.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Reduce console output.",
    )
    return parser.parse_args()


def _resolve_source_files(cli_sources: Sequence[str] | None) -> List[Path]:
    if cli_sources:
        return [Path(item).resolve() for item in cli_sources]
    return [path.resolve() for path in DEFAULT_SOURCES]


def _resolve_output_dirs(cli_output_dirs: Sequence[str] | None) -> List[Path]:
    if cli_output_dirs:
        return [Path(item).resolve() for item in cli_output_dirs]
    return [path.resolve() for path in DEFAULT_OUTPUT_DIRS]


def main() -> None:
    args = _parse_cli_args()
    source_files = _resolve_source_files(args.sources)
    output_dirs = _resolve_output_dirs(args.output_dirs)

    generator = APIDocumentGenerator(
        source_files=source_files,
        output_dirs=output_dirs,
        clean_stale=not args.no_clean,
        quiet=args.quiet,
    )

    apis = generator.extract_apis()
    if not apis:
        print("没有找到任何带有docstring的API函数")
        return

    generator.generate_markdown_docs()

    if not args.quiet:
        print("\n✅ 文档生成完成！")
        print(f"📄 共处理 {len(apis)} 个API")
        print("📁 输出目录:")
        for path in output_dirs:
            print(f"  - {path}")


if __name__ == "__main__":
    main()
