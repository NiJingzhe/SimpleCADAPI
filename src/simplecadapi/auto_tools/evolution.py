#!/usr/bin/env python3
"""Automatically extract modeling functions from a script and append them to `evolve.py`."""

from pathlib import Path

EVOLVE_FILE = Path(__file__).parent.parent / "evolve.py"


def extract_source_code_from_file(file_path: Path):
    """Read the source text from a file."""
    with open(file_path, "r", encoding="utf-8") as f:
        source_code = f.read()
    return source_code


def extract_functions_from_source(source_code: str):
    """Extract full function implementations from source code."""
    import ast

    class FunctionBodyExtractor(ast.NodeVisitor):
        def __init__(self):
            self.function_bodies = {}

        def visit_FunctionDef(self, node):
            # 注意：lineno 和 end_lineno 是从1开始的
            if hasattr(node, "end_lineno"):
                lines = source_code.splitlines()
                func_code = "\n".join(lines[node.lineno - 1 : node.end_lineno])
                self.function_bodies[node.name] = func_code
            self.generic_visit(node)

    tree = ast.parse(source_code)
    extractor = FunctionBodyExtractor()
    extractor.visit(tree)
    return [function for function in extractor.function_bodies.values()]


def extract_import_from_source(source_code: str) -> list[str]:
    """Extract module-level import statements from source code."""
    import ast

    try:
        tree = ast.parse(source_code)
    except SyntaxError as e:
        print(f"警告: 解析源码时出现语法错误: {e}")
        return []  # 或者可以抛出异常

    imports = []

    # 遍历模块主体 (module.body)
    for node in tree.body:
        # 检查是否是导入语句
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(f"import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            module_name = node.module if node.module else ""
            for alias in node.names:
                imports.append(f"from {module_name} import {alias.name}")
        elif isinstance(node, ast.FunctionDef) or isinstance(node, ast.ClassDef):
            # 一旦遇到函数或类定义，就认为头部导入部分结束
            # 根据Python惯例，导入通常在文件顶部
            break

    return imports


def combine_import_into_function(imports: list, function: str):
    """Insert import statements into a function body string."""
    if not imports:
        return function

    lines = function.splitlines()
    if not lines:
        return function

    insert_at = _find_import_insert_index(lines)
    import_lines = [f"    {item}" for item in imports]

    merged_lines = lines[:insert_at] + [""] + import_lines + [""] + lines[insert_at:]
    return "\n".join(merged_lines)


def _find_import_insert_index(lines: list[str]) -> int:
    """Find where imports should be inserted inside a function."""
    if len(lines) <= 1:
        return len(lines)

    index = 1
    while index < len(lines) and not lines[index].strip():
        index += 1

    if index >= len(lines):
        return 1

    stripped = lines[index].strip()
    if not (stripped.startswith('"""') or stripped.startswith("'''")):
        return 1

    quote = '"""' if stripped.startswith('"""') else "'''"

    if stripped.count(quote) >= 2 and len(stripped) > len(quote) * 2:
        return index + 1

    index += 1
    while index < len(lines):
        if quote in lines[index]:
            return index + 1
        index += 1

    return 1


def main():

    import argparse

    parser = argparse.ArgumentParser(
        description="Extract functions from a Python file and add them to evolve.py."
    )

    parser.add_argument(
        "file_path", type=str, help="Path to the Python file to extract functions from."
    )
    parser.add_argument(
        "--evolve_file",
        type=str,
        default=str(EVOLVE_FILE),
        help="Path to the evolve.py file to add functions to.",
    )

    args = parser.parse_args()

    file_path = Path(args.file_path)
    evolve_file = Path(args.evolve_file)

    if not file_path.exists():
        print(f"错误: 文件 {file_path} 不存在。")
        exit(1)

    if not evolve_file.exists():
        print(f"错误: evolve.py 文件 {evolve_file} 不存在。")
        exit(1)

    # 提取源代码
    source_code = extract_source_code_from_file(file_path)
    if not source_code.strip():
        print(f"警告: 文件 {file_path} 为空或只包含空白字符。")
        exit(1)

    # 提取函数
    function_body = extract_functions_from_source(source_code)[0]
    if not function_body:
        print(f"警告: 文件 {file_path} 中未找到任何函数。")
        exit(1)

    # 提取导入语句
    imports = extract_import_from_source(source_code)

    result_function = combine_import_into_function(imports, function_body)

    # 追加到 evolve.py
    with open(evolve_file, "a", encoding="utf-8") as f:
        f.write("\n\n" + result_function + "\n")


if __name__ == "__main__":
    main()
