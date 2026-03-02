#!/usr/bin/env python3
"""
自动化导出脚本 - 更新 __init__.py 文件
每次 operations.py 有新的 API 函数时，自动更新 __init__.py 中的导入和导出

使用方法:
    python make_export.py              # 标准模式
    python make_export.py --dry-run    # 预览模式，不实际修改文件
    python make_export.py --force      # 强制模式，跳过确认
    python make_export.py --help       # 显示帮助
"""

import re
import ast
import argparse
from pathlib import Path
from typing import List, Dict, Tuple

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_DIR = PROJECT_ROOT / "simplecadapi"
OPERATIONS_FILE = SRC_DIR / "operations.py"
EVOLVE_FILE = SRC_DIR / "evolve.py"
INIT_FILE = SRC_DIR / "__init__.py"

# 函数分类规则
FUNCTION_CATEGORIES = {
    "基础几何创建": [
        "make_point_",
        "make_line_",
        "make_segment_",
        "make_circle_",
        "make_rectangle_",
        "make_box_",
        "make_cylinder_",
        "make_sphere_",
        "make_angle_arc_",
        "make_three_point_arc_",
        "make_spline_",
        "make_polyline_",
        "make_helix_",
        "make_face_from_wire_",
        "make_wire_from_edges_",
        "make_cone_",
    ],
    "变换操作": ["translate_", "rotate_", "scale_", "mirror_"],
    "3D操作": ["extrude_", "revolve_", "loft_", "sweep_", "helical_sweep_"],
    "标签和选择": ["set_tag", "select_faces_", "select_edges_", "get_tag"],
    "布尔运算": ["union_", "cut_", "intersect_", "difference_"],
    "导出": ["export_"],
    "高级特征操作": ["fillet_", "chamfer_", "shell_", "pattern_", "array_"],
}

# 别名映射规则
ALIAS_RULES = {
    "make_point_rvertex": "create_point",
    "make_line_redge": "create_line",
    "make_segment_redge": "create_segment",
    "make_segment_rwire": "create_segment_wire",
    "make_circle_redge": "create_circle_edge",
    "make_circle_rwire": "create_circle_wire",
    "make_circle_rface": "create_circle_face",
    "make_rectangle_rwire": "create_rectangle_wire",
    "make_rectangle_rface": "create_rectangle_face",
    "make_box_rsolid": "create_box",
    "make_cylinder_rsolid": "create_cylinder",
    "make_sphere_rsolid": "create_sphere",
    "make_angle_arc_redge": "create_angle_arc",
    "make_angle_arc_rwire": "create_angle_arc_wire",
    "make_three_point_arc_redge": "create_arc",
    "make_three_point_arc_rwire": "create_arc_wire",
    "make_spline_redge": "create_spline",
    "make_spline_rwire": "create_spline_wire",
    "make_polyline_redge": "create_polyline",
    "make_polyline_rwire": "create_polyline_wire",
    "make_helix_redge": "create_helix",
    "make_helix_rwire": "create_helix_wire",
    "make_face_from_wire_rface": "create_face_from_wire",
    "make_wire_from_edges_rwire": "create_wire_from_edges",
    "translate_shape": "translate",
    "rotate_shape": "rotate",
    "extrude_rsolid": "extrude",
    "revolve_rsolid": "revolve",
    "union_rsolidlist": "union",
    "cut_rsolidlist": "cut",
    "intersect_rsolidlist": "intersect",
    "export_step": "to_step",
    "export_stl": "to_stl",
}


def extract_functions_from_operations() -> List[str]:
    """从 operations.py 文件中提取所有函数名"""
    functions: List[str] = []

    if not OPERATIONS_FILE.exists():
        print(f"错误: {OPERATIONS_FILE} 文件不存在")
        return functions

    with open(OPERATIONS_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # 使用正则表达式提取函数定义
    pattern = r"^def\s+(\w+)\s*\("
    matches = re.findall(pattern, content, re.MULTILINE)

    # 过滤掉私有函数和内部函数
    for func_name in matches:
        if not func_name.startswith("_"):
            functions.append(func_name)

    return sorted(functions)


def extract_functions_from_evolve() -> List[str]:
    """从 operations.py 文件中提取所有函数名"""
    functions: List[str] = []

    if not EVOLVE_FILE.exists():
        print(f"错误: {EVOLVE_FILE} 文件不存在")
        return functions

    with open(EVOLVE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    # 使用正则表达式提取函数定义
    pattern = r"^def\s+(\w+)\s*\("
    matches = re.findall(pattern, content, re.MULTILINE)

    # 过滤掉私有函数和内部函数
    for func_name in matches:
        if not func_name.startswith("_"):
            functions.append(func_name)

    return sorted(functions)


def extract_functions_from_core() -> List[str]:
    """从 core.py 文件中提取需要导出的函数和类"""
    core_file = SRC_DIR / "core.py"
    functions: List[str] = []

    if not core_file.exists():
        print(f"警告: {core_file} 文件不存在")
        return functions

    with open(core_file, "r", encoding="utf-8") as f:
        content = f.read()

    # 提取类定义
    class_pattern = r"^class\s+(\w+)(?:\([^)]*\))?:"
    class_matches = re.findall(class_pattern, content, re.MULTILINE)

    # 提取函数定义
    func_pattern = r"^def\s+(\w+)\s*\("
    func_matches = re.findall(func_pattern, content, re.MULTILINE)

    # 过滤掉私有函数和类
    for name in class_matches + func_matches:
        if not name.startswith("_"):
            functions.append(name)

    return sorted(functions)


def categorize_functions(functions: List[str]) -> Dict[str, List[str]]:
    """将函数按类别分组"""
    categorized: Dict[str, List[str]] = {}

    for category, prefixes in FUNCTION_CATEGORIES.items():
        categorized[category] = []
        for func in functions:
            for prefix in prefixes:
                if func.startswith(prefix):
                    categorized[category].append(func)
                    break

    # 处理未分类的函数
    categorized_flat = []
    for funcs in categorized.values():
        categorized_flat.extend(funcs)

    uncategorized = [f for f in functions if f not in categorized_flat]
    if uncategorized:
        categorized["其他"] = uncategorized

    return categorized


def generate_core_imports() -> str:
    """生成 core 模块的导入语句"""
    core_exports = [
        "CoordinateSystem",
        "SimpleWorkplane",
        "Vertex",
        "Edge",
        "Wire",
        "Face",
        "Solid",
        "AnyShape",
        "TaggedMixin",
        "get_current_cs",
        "WORLD_CS",
    ]

    import_lines = ["from .core import ("]
    import_lines.append("    # 核心类")

    classes = [
        "CoordinateSystem",
        "SimpleWorkplane",
        "Vertex",
        "Edge",
        "Wire",
        "Face",
        "Solid",
        "AnyShape",
        "TaggedMixin",
    ]

    for cls in classes:
        import_lines.append(f"    {cls},")

    import_lines.append("")
    import_lines.append("    # 坐标系函数")
    import_lines.append("    get_current_cs,")
    import_lines.append("    WORLD_CS,")
    import_lines.append(")")

    return "\n".join(import_lines)


def generate_operations_imports(categorized_functions: Dict[str, List[str]]) -> str:
    """生成 operations 模块的导入语句"""
    import_lines = ["from .operations import ("]

    for category, functions in categorized_functions.items():
        if not functions:
            continue

        import_lines.append(f"    # {category}")
        for func in functions:
            import_lines.append(f"    {func},")
        import_lines.append("")

    # 移除最后一个空行
    if import_lines[-1] == "":
        import_lines.pop()

    import_lines.append(")")

    return "\n".join(import_lines)


def generate_evolve_imports(categorized_functions: Dict[str, List[str]]) -> str:
    """生成 evolve 模块的导入语句"""
    import_lines = ["from .evolve import ("]

    for category, functions in categorized_functions.items():
        if not functions:
            continue

        import_lines.append(f"    # {category}")
        for func in functions:
            import_lines.append(f"    {func},")
        import_lines.append("")

    # 移除最后一个空行
    if import_lines[-1] == "":
        import_lines.pop()

    import_lines.append(")")

    return "\n".join(import_lines)


def generate_aliases(functions: List[str]) -> str:
    """生成别名定义"""
    alias_lines = []

    # 首先添加固定的别名
    alias_lines.append("# 便于使用的别名")
    alias_lines.append("Workplane = SimpleWorkplane")
    alias_lines.append("")

    # 按类别组织别名
    alias_categories: Dict[str, List[Tuple[str, str]]] = {}
    for func in functions:
        if func in ALIAS_RULES:
            alias = ALIAS_RULES[func]
            # 根据函数类型分类
            if func.startswith("make_"):
                category = "创建函数别名"
            elif func.startswith("translate_") or func.startswith("rotate_"):
                category = "变换操作别名"
            elif func.startswith("extrude_") or func.startswith("revolve_"):
                category = "3D操作别名"
            elif (
                func.startswith("union_")
                or func.startswith("cut_")
                or func.startswith("intersect_")
            ):
                category = "布尔运算别名"
            elif func.startswith("export_"):
                category = "导出别名"
            else:
                category = "其他别名"

            if category not in alias_categories:
                alias_categories[category] = []
            alias_categories[category].append((func, alias))

    # 生成别名代码
    for category, aliases in alias_categories.items():
        alias_lines.append(f"# {category}")
        for func, alias in aliases:
            alias_lines.append(f"{alias} = {func}")
        alias_lines.append("")

    return "\n".join(alias_lines)


def generate_all_list(functions: List[str]) -> str:
    """生成 __all__ 列表"""
    all_lines = ["__all__ = ["]

    # 核心导出
    all_lines.append("    # 核心类")
    core_exports = [
        "CoordinateSystem",
        "SimpleWorkplane",
        "Workplane",
        "Vertex",
        "Edge",
        "Wire",
        "Face",
        "Solid",
        "AnyShape",
        "TaggedMixin",
    ]
    for item in core_exports:
        all_lines.append(f'    "{item}",')

    all_lines.append("")
    all_lines.append("    # 坐标系")
    all_lines.append('    "get_current_cs",')
    all_lines.append('    "WORLD_CS",')
    all_lines.append("")

    # 按类别添加函数
    categorized = categorize_functions(functions)
    for category, funcs in categorized.items():
        if not funcs:
            continue
        all_lines.append(f"    # {category}")
        for func in funcs:
            all_lines.append(f'    "{func}",')
        all_lines.append("")

    # 添加别名
    all_lines.append("    # 别名")
    aliases = []
    for func in functions:
        if func in ALIAS_RULES:
            aliases.append(ALIAS_RULES[func])

    for alias in sorted(aliases):
        all_lines.append(f'    "{alias}",')

    all_lines.append("]")

    return "\n".join(all_lines)


def generate_init_file(
    operations_functions: List[str], evolve_functions: List[str]
) -> str:
    """生成完整的 __init__.py 文件内容"""
    lines = []

    # 文件头注释
    lines.append('"""')
    lines.append("SimpleCAD API - 简化的CAD建模Python API")
    lines.append("基于CADQuery实现，提供直观的几何建模接口")
    lines.append('"""')
    lines.append("")

    # 核心模块导入
    lines.append(generate_core_imports())
    lines.append("")

    # operations 模块导入
    if operations_functions:
        categorized_operations = categorize_functions(operations_functions)
        lines.append(generate_operations_imports(categorized_operations))
        lines.append("")

    # evolve 模块导入
    if evolve_functions:
        categorized_evolve = categorize_functions(evolve_functions)
        lines.append(generate_evolve_imports(categorized_evolve))
        lines.append("")

    # 版本信息
    lines.append('__author__ = "SimpleCAD API Team"')
    lines.append(
        '__description__ = "Simplified CAD modeling Python API based on CADQuery"'
    )
    lines.append("")

    # 合并所有函数用于别名和 __all__ 列表
    all_functions = operations_functions + evolve_functions

    # 别名定义
    lines.append(generate_aliases(all_functions))
    lines.append("")

    # __all__ 列表
    lines.append(generate_all_list(all_functions))
    lines.append("")

    return "\n".join(lines)


def backup_init_file():
    """备份当前的 __init__.py 文件"""
    if INIT_FILE.exists():
        backup_file = INIT_FILE.with_suffix(".py.bak")
        with open(INIT_FILE, "r", encoding="utf-8") as src:
            with open(backup_file, "w", encoding="utf-8") as dst:
                dst.write(src.read())
        print(f"已备份原文件到: {backup_file}")


def check_syntax(file_path: Path) -> bool:
    """检查生成的Python文件语法是否正确"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        ast.parse(content)
        return True
    except SyntaxError as e:
        print(f"语法错误: {e}")
        return False
    except Exception as e:
        print(f"文件检查失败: {e}")
        return False


def compare_with_existing(new_functions: List[str]) -> Tuple[List[str], List[str]]:
    """比较新函数列表与现有的函数列表"""
    if not INIT_FILE.exists():
        return new_functions, []

    try:
        with open(INIT_FILE, "r", encoding="utf-8") as f:
            content = f.read()

        # 从现有文件中提取函数名（从 from .operations import 和 from .evolve import 部分）
        existing_functions = []

        # 提取 operations 模块的函数
        operations_match = re.search(
            r"from \.operations import \((.*?)\)", content, re.DOTALL
        )
        if operations_match:
            operations_content = operations_match.group(1)
            operations_functions = re.findall(
                r"^\s*(\w+),?\s*$", operations_content, re.MULTILINE
            )
            operations_functions = [
                f.rstrip(",") for f in operations_functions if not f.startswith("#")
            ]
            existing_functions.extend(operations_functions)

        # 提取 evolve 模块的函数
        evolve_match = re.search(r"from \.evolve import \((.*?)\)", content, re.DOTALL)
        if evolve_match:
            evolve_content = evolve_match.group(1)
            evolve_functions = re.findall(
                r"^\s*(\w+),?\s*$", evolve_content, re.MULTILINE
            )
            evolve_functions = [
                f.rstrip(",") for f in evolve_functions if not f.startswith("#")
            ]
            existing_functions.extend(evolve_functions)

        new_additions = [f for f in new_functions if f not in existing_functions]
        removed_functions = [f for f in existing_functions if f not in new_functions]

        return new_additions, removed_functions
    except Exception as e:
        print(f"比较文件时出错: {e}")

    return new_functions, []


def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="自动更新 SimpleCAD API 的 __init__.py 文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python make_export.py              # 标准模式
  python make_export.py --dry-run    # 预览模式，不实际修改文件
  python make_export.py --force      # 强制模式，跳过确认
  python make_export.py --verbose    # 详细输出模式
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="预览模式，显示将要进行的更改但不实际修改文件",
    )

    parser.add_argument(
        "--show-api-only",
        action="store_true",
        help="仅显示 API 函数，不生成 __init__.py 文件",
    )

    parser.add_argument(
        "--force", action="store_true", help="强制模式，跳过所有确认提示"
    )

    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出模式")

    parser.add_argument(
        "--backup", default=True, help="是否创建备份文件 (默认: 创建备份)"
    )

    return parser.parse_args()


def main():
    """主函数"""
    args = parse_arguments()

    if args.verbose:
        print("🚀 开始更新 __init__.py 文件...")

    # 检查必要文件是否存在
    if not OPERATIONS_FILE.exists():
        print(f"❌ 错误: {OPERATIONS_FILE} 文件不存在")
        return

    # 提取 operations.py 中的函数
    operations_functions = extract_functions_from_operations()
    if args.verbose:
        print(f"✅ 从 operations.py 找到 {len(operations_functions)} 个函数")

    # 提取 evolve.py 中的函数
    if args.verbose:
        print("📋 提取 evolve.py 中的函数...")
    evolve_functions = extract_functions_from_evolve()
    if args.verbose:
        print(f"✅ 从 evolve.py 找到 {len(evolve_functions)} 个函数")

    if not operations_functions and not evolve_functions:
        print("❌ 未找到任何函数，退出")
        return

    # 合并所有函数用于比较
    all_functions = operations_functions + evolve_functions

    # 比较变更
    new_additions, removed_functions = compare_with_existing(all_functions)

    if new_additions:
        if args.verbose:
            print(f"\n🆕 新增函数 ({len(new_additions)} 个):")
            for func in new_additions:
                print(f"  + {func}")

    if removed_functions:
        if args.verbose:
            print(f"\n🗑️  删除函数 ({len(removed_functions)} 个):")
            for func in removed_functions:
                print(f"  - {func}")

    # 显示函数分类（详细模式）
    if args.verbose:
        print("\n📊 函数分类统计:")
        print("  Operations 模块:")
        categorized_operations = categorize_functions(operations_functions)
        for category, funcs in categorized_operations.items():
            if funcs:
                print(f"    {category}: {len(funcs)} 个函数")
                for func in funcs[:3]:  # 只显示前3个
                    print(f"      - {func}")
                if len(funcs) > 3:
                    print(f"      ... 和其他 {len(funcs) - 3} 个函数")

        print("  Evolve 模块:")
        categorized_evolve = categorize_functions(evolve_functions)
        for category, funcs in categorized_evolve.items():
            if funcs:
                print(f"    {category}: {len(funcs)} 个函数")
                for func in funcs[:3]:  # 只显示前3个
                    print(f"      - {func}")
                if len(funcs) > 3:
                    print(f"      ... 和其他 {len(funcs) - 3} 个函数")

    # 预览模式
    if args.dry_run:
        print("\n👁️  预览模式 - 将要进行的更改:")
        new_content = generate_init_file(operations_functions, evolve_functions)
        print(f"  生成的文件大小: {len(new_content)} 字符")
        print(f"  Operations 函数数: {len(operations_functions)}")
        print(f"  Evolve 函数数: {len(evolve_functions)}")
        print(f"  总函数数: {len(all_functions)}")
        print(f"  别名数: {len([f for f in all_functions if f in ALIAS_RULES])}")
        print("  (使用 --verbose 查看详细信息)")
        print("\n💡 要实际执行更改，请移除 --dry-run 参数")
        return

    if args.show_api_only:
        print("\n📜 API 函数列表 (按模块和类别分组):")

        # Operations 模块函数
        print("\n🔹 Operations 模块:")
        categorized_operations = categorize_functions(operations_functions)
        total_operations = 0

        for category, funcs in categorized_operations.items():
            if funcs:
                print(f"\n  {category} ({len(funcs)} 个函数):")
                for func in sorted(funcs):
                    print(f"    - {func}")
                total_operations += len(funcs)

        # Evolve 模块函数
        print("\n🔹 Evolve 模块:")
        categorized_evolve = categorize_functions(evolve_functions)
        total_evolve = 0

        for category, funcs in categorized_evolve.items():
            if funcs:
                print(f"\n  {category} ({len(funcs)} 个函数):")
                for func in sorted(funcs):
                    print(f"    - {func}")
                total_evolve += len(funcs)

        print(
            f"\n📊 总计: Operations {total_operations} 个函数, Evolve {total_evolve} 个函数, 总计 {total_operations + total_evolve} 个函数"
        )

        return

    # 备份原文件
    if args.backup:
        backup_init_file()

    # 生成新的 __init__.py 文件
    print("\n🔄 生成新的 __init__.py 文件...")
    new_content = generate_init_file(operations_functions, evolve_functions)

    # 写入文件
    with open(INIT_FILE, "w", encoding="utf-8") as f:
        f.write(new_content)

    # 语法检查
    print("🔍 检查生成文件的语法...")
    if check_syntax(INIT_FILE):
        print("✅ 语法检查通过")
    else:
        print("❌ 语法检查失败，请检查生成的文件")
        return

    print(f"✅ 已更新 {INIT_FILE}")
    print("🎉 更新完成！")

    # 显示统计信息
    print(f"\n📈 统计信息:")
    print(f"  Operations 函数数: {len(operations_functions)}")
    print(f"  Evolve 函数数: {len(evolve_functions)}")
    print(f"  总函数数: {len(all_functions)}")
    print(f"  别名数: {len([f for f in all_functions if f in ALIAS_RULES])}")
    categorized_operations = categorize_functions(operations_functions)
    categorized_evolve = categorize_functions(evolve_functions)
    print(
        f"  Operations 类别数: {len([c for c, f in categorized_operations.items() if f])}"
    )
    print(f"  Evolve 类别数: {len([c for c, f in categorized_evolve.items() if f])}")

    # 建议下一步操作
    print(f"\n💡 建议:")
    print(f"  1. 检查生成的 {INIT_FILE} 文件")
    print(f"  2. 运行测试确保所有导入正常工作")
    if args.backup:
        print(f"  3. 如有问题，可以从备份文件 {INIT_FILE}.bak 恢复")


if __name__ == "__main__":
    main()
