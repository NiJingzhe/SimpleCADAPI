#!/usr/bin/env python3
"""Update `simplecadapi/__init__.py` exports from source modules.

This tool supports two common workflows:
- `--show-api-only`: inspect the public API grouped by module and category.
- default mode: regenerate `__init__.py` from the current module set.

It reads module files directly from the installed package location, so it works both
from a source checkout and from an installed virtual environment.
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Mapping, Sequence, Tuple


PACKAGE_NAME = "simplecadapi"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
INIT_FILE = PACKAGE_ROOT / "__init__.py"

CORE_EXPORTS = [
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

MODULE_ORDER = ("operations", "evolve", "constraints", "field", "ql")
MODULE_LABELS = {
    "operations": "Operations",
    "evolve": "Evolve",
    "constraints": "Constraints",
    "field": "Field",
    "ql": "QL",
}

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
        "make_field_surface_",
    ],
    "变换操作": ["translate_", "rotate_", "scale_", "mirror_"],
    "3D操作": ["extrude_", "revolve_", "loft_", "sweep_", "helical_sweep_"],
    "标签和选择": ["set_tag", "select_faces_", "select_edges_", "get_tag"],
    "布尔运算": ["union_", "cut_", "intersect_", "difference_"],
    "导出": ["export_", "render_"],
    "高级特征操作": ["fillet_", "chamfer_", "shell_", "pattern_", "array_"],
}

FIELD_CATEGORIES = {
    "基础场函数": [
        "make_sphere_",
        "make_ellipsoid_",
        "make_box_",
        "make_capsule_",
    ],
    "布尔运算": [
        "union_",
        "intersect_",
        "subtract_",
        "smooth_union_",
        "smooth_subtract_",
    ],
    "变换操作": ["translate_", "scale_", "rotate_"],
    "评估和分析": ["eval_", "bounds_"],
}

QL_CATEGORIES = {
    "标签与元数据谓词": ["tag", "meta", "geo"],
    "逻辑组合": ["and_", "or_", "not_"],
    "查询与取值": ["select", "value"],
}

TAIL_CONSTRAINT_FUNCTIONS = ("stack",)
CONSTRAINTS_CLASS_ORDER = (
    "Assembly",
    "AssemblyResult",
    "SolveReport",
    "PartHandle",
    "PointAnchor",
    "AxisAnchor",
)

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
    "make_polyline_rwire": "create_polyline_wire",
    "make_helix_redge": "create_helix",
    "make_helix_rwire": "create_helix_wire",
    "make_face_from_wire_rface": "create_face_from_wire",
    "make_wire_from_edges_rwire": "create_wire_from_edges",
    "make_field_surface_rsolid": "create_field_surface",
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


@dataclass(frozen=True)
class ModuleInventory:
    name: str
    display_name: str
    functions: List[str] = field(default_factory=list)
    classes: List[str] = field(default_factory=list)


def _module_file(module_name: str, package_root: Path | None = None) -> Path:
    root = package_root.resolve() if package_root is not None else PACKAGE_ROOT
    return root / f"{module_name}.py"


def _parse_module(file_path: Path) -> ast.Module | None:
    if not file_path.exists():
        print(f"警告: {file_path} 文件不存在")
        return None

    try:
        source = file_path.read_text(encoding="utf-8")
        return ast.parse(source, filename=str(file_path))
    except Exception as exc:
        print(f"警告: 解析 {file_path} 失败: {exc}")
        return None


def extract_public_functions(file_path: Path) -> List[str]:
    tree = _parse_module(file_path)
    if tree is None:
        return []

    functions: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and not node.name.startswith("_"):
            functions.append(node.name)
    return functions


def extract_public_classes(file_path: Path) -> List[str]:
    tree = _parse_module(file_path)
    if tree is None:
        return []

    classes: List[str] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
            classes.append(node.name)
    return classes


def collect_api_inventory(
    package_root: Path | None = None,
) -> Dict[str, ModuleInventory]:
    root = package_root.resolve() if package_root is not None else PACKAGE_ROOT
    inventory: Dict[str, ModuleInventory] = {}

    for module_name in MODULE_ORDER:
        file_path = _module_file(module_name, root)
        inventory[module_name] = ModuleInventory(
            name=module_name,
            display_name=MODULE_LABELS[module_name],
            functions=extract_public_functions(file_path),
            classes=(
                extract_public_classes(file_path)
                if module_name == "constraints"
                else []
            ),
        )

    return inventory


def categorize_functions(
    functions: Sequence[str],
    category_rules: Mapping[str, Sequence[str]],
    fallback_label: str = "其他",
) -> Dict[str, List[str]]:
    categorized: Dict[str, List[str]] = {name: [] for name in category_rules}

    for func in functions:
        matched = False
        for category, prefixes in category_rules.items():
            if any(func.startswith(prefix) for prefix in prefixes):
                categorized[category].append(func)
                matched = True
                break
        if not matched:
            categorized.setdefault(fallback_label, []).append(func)

    return {name: sorted(funcs) for name, funcs in categorized.items() if funcs}


def categorize_constraints(functions: Sequence[str]) -> Dict[str, List[str]]:
    if not functions:
        return {}
    return {"声明式装配约束": sorted(functions)}


def ordered_constraint_classes(classes: Sequence[str]) -> List[str]:
    priority = {name: index for index, name in enumerate(CONSTRAINTS_CLASS_ORDER)}
    return sorted(classes, key=lambda name: (priority.get(name, len(priority)), name))


def categorize_module(
    module_name: str, functions: Sequence[str]
) -> Dict[str, List[str]]:
    if module_name in {"operations", "evolve"}:
        return categorize_functions(functions, FUNCTION_CATEGORIES)
    if module_name == "constraints":
        return categorize_constraints(functions)
    if module_name == "field":
        return categorize_functions(functions, FIELD_CATEGORIES)
    if module_name == "ql":
        return categorize_functions(functions, QL_CATEGORIES)
    return {"其他": list(functions)} if functions else {}


def generate_core_imports() -> str:
    lines = ["from .core import (", "    # 核心类"]

    for name in CORE_EXPORTS[:-2]:
        lines.append(f"    {name},")

    lines.append("    # 坐标系函数")
    for name in CORE_EXPORTS[-2:]:
        lines.append(f"    {name},")
    lines.append(")")
    return "\n".join(lines)


def _render_import_block(module_name: str, categorized: Dict[str, List[str]]) -> str:
    lines = [f"from .{module_name} import ("]
    for category, functions in categorized.items():
        lines.append(f"    # {category}")
        for func in functions:
            lines.append(f"    {func},")
        lines.append("")

    if lines[-1] == "":
        lines.pop()
    lines.append(")")
    return "\n".join(lines)


def generate_constraints_imports(
    functions: Sequence[str], classes: Sequence[str]
) -> str:
    lines = ["from .constraints import (", "    # 声明式装配约束"]

    tail = sorted(name for name in functions if name in TAIL_CONSTRAINT_FUNCTIONS)
    head = sorted(name for name in functions if name not in TAIL_CONSTRAINT_FUNCTIONS)

    for name in head:
        lines.append(f"    {name},")
    for name in ordered_constraint_classes(classes):
        lines.append(f"    {name},")
    for name in tail:
        lines.append(f"    {name},")

    lines.append(")")
    return "\n".join(lines)


def generate_aliases(functions: Sequence[str]) -> str:
    alias_lines = ["# 便于使用的别名", "Workplane = SimpleWorkplane", ""]

    alias_categories: Dict[str, List[Tuple[str, str]]] = {}
    for func in functions:
        alias = ALIAS_RULES.get(func)
        if alias is None:
            continue

        if func.startswith("make_"):
            category = "创建函数别名"
        elif func.startswith(("translate_", "rotate_")):
            category = "变换操作别名"
        elif func.startswith(("extrude_", "revolve_")):
            category = "3D操作别名"
        elif func.startswith(("union_", "cut_", "intersect_")):
            category = "布尔运算别名"
        elif func.startswith("export_"):
            category = "导出别名"
        else:
            category = "其他别名"

        alias_categories.setdefault(category, []).append((func, alias))

    for category, aliases in alias_categories.items():
        alias_lines.append(f"# {category}")
        for func, alias in sorted(aliases, key=lambda item: item[1]):
            alias_lines.append(f"{alias} = {func}")
        alias_lines.append("")

    if alias_lines[-1] == "":
        alias_lines.pop()
    return "\n".join(alias_lines)


def generate_all_list(
    operations_functions: Sequence[str],
    evolve_functions: Sequence[str],
    constraints_functions: Sequence[str],
    constraints_classes: Sequence[str],
) -> str:
    all_lines = ["__all__ = [", "    # 核心类"]

    core_public = [
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
    for name in core_public:
        all_lines.append(f'    "{name}",')

    all_lines.extend(
        ["", "    # 坐标系", '    "get_current_cs",', '    "WORLD_CS",', ""]
    )

    public_functions = list(operations_functions) + list(evolve_functions)
    categorized = categorize_functions(public_functions, FUNCTION_CATEGORIES)
    for category, funcs in categorized.items():
        all_lines.append(f"    # {category}")
        for func in funcs:
            all_lines.append(f'    "{func}",')
        all_lines.append("")

    all_lines.append("    # 声明式装配约束")
    tail = sorted(
        name for name in constraints_functions if name in TAIL_CONSTRAINT_FUNCTIONS
    )
    head = sorted(
        name for name in constraints_functions if name not in TAIL_CONSTRAINT_FUNCTIONS
    )
    for name in (
        list(head) + ordered_constraint_classes(constraints_classes) + list(tail)
    ):
        all_lines.append(f'    "{name}",')

    all_lines.extend(['    "field",', '    "ql",', "", "    # 别名"])

    aliases = sorted(
        ALIAS_RULES[func] for func in public_functions if func in ALIAS_RULES
    )
    for alias in aliases:
        all_lines.append(f'    "{alias}",')

    all_lines.append("]")
    return "\n".join(all_lines)


def generate_init_file(inventory: Dict[str, ModuleInventory]) -> str:
    operations = inventory["operations"].functions
    evolve = inventory["evolve"].functions
    constraints = inventory["constraints"].functions
    constraint_classes = inventory["constraints"].classes

    lines = [
        '"""',
        "SimpleCAD API - 简化的CAD建模Python API",
        "基于CADQuery实现，提供直观的几何建模接口",
        '"""',
        "",
        generate_core_imports(),
        "",
    ]

    if operations:
        lines.append(
            _render_import_block(
                "operations", categorize_module("operations", operations)
            )
        )
        lines.append("")

    if evolve:
        lines.append(
            _render_import_block("evolve", categorize_module("evolve", evolve))
        )
        lines.append("")

    if constraints or constraint_classes:
        lines.append(generate_constraints_imports(constraints, constraint_classes))
        lines.append("")

    lines.extend(
        [
            "from . import field",
            "from . import ql",
            "",
            '__author__ = "SimpleCAD API Team"',
            '__description__ = "Simplified CAD modeling Python API based on CADQuery"',
            "",
            generate_aliases(list(operations) + list(evolve)),
            "",
            generate_all_list(operations, evolve, constraints, constraint_classes),
            "",
        ]
    )

    return "\n".join(lines)


def backup_init_file(file_path: Path = INIT_FILE) -> None:
    if not file_path.exists():
        return

    backup_file = file_path.with_suffix(".py.bak")
    backup_file.write_text(file_path.read_text(encoding="utf-8"), encoding="utf-8")
    print(f"已备份原文件到: {backup_file}")


def check_syntax(file_path: Path) -> bool:
    try:
        ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        return True
    except SyntaxError as exc:
        print(f"语法错误: {exc}")
        return False
    except Exception as exc:
        print(f"文件检查失败: {exc}")
        return False


def extract_existing_auto_exports(file_path: Path = INIT_FILE) -> List[str]:
    if not file_path.exists():
        return []

    try:
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
    except Exception as exc:
        print(f"比较文件时出错: {exc}")
        return []

    symbols: List[str] = []
    managed_modules = {"operations", "evolve", "constraints"}

    for node in tree.body:
        if not isinstance(node, ast.ImportFrom) or node.level != 1:
            continue

        if node.module in managed_modules:
            for alias in node.names:
                if alias.name != "*":
                    symbols.append(alias.name)
            continue

        if node.module is None:
            for alias in node.names:
                if alias.name in {"field", "ql"}:
                    symbols.append(alias.name)

    return sorted(dict.fromkeys(symbols))


def compare_with_existing(target_symbols: Sequence[str]) -> Tuple[List[str], List[str]]:
    existing = extract_existing_auto_exports()
    target = sorted(dict.fromkeys(target_symbols))
    new_additions = [name for name in target if name not in existing]
    removed = [name for name in existing if name not in target]
    return new_additions, removed


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="自动更新 SimpleCAD API 的 __init__.py 文件",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
使用示例:
  python make_export.py                   # 标准模式
  python make_export.py --dry-run         # 预览模式，不实际修改文件
  python make_export.py --show-api-only   # 只显示 API 列表
  python make_export.py --force           # 强制模式，跳过确认
  python make_export.py --verbose         # 详细输出模式
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
        "--force",
        action="store_true",
        help="强制模式，跳过所有确认提示",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="详细输出模式",
    )
    parser.add_argument(
        "--backup",
        dest="backup",
        action="store_true",
        default=True,
        help="创建备份文件 (默认: 创建备份)",
    )
    parser.add_argument(
        "--no-backup",
        dest="backup",
        action="store_false",
        help="不创建备份文件",
    )
    return parser.parse_args()


def _print_module_summary(module_name: str, inventory: ModuleInventory) -> int:
    categorized = categorize_module(module_name, inventory.functions)
    total = 0

    print(f"\n🔹 {inventory.display_name} 模块:")
    for category, funcs in categorized.items():
        print(f"\n  {category} ({len(funcs)} 个函数):")
        for func in sorted(funcs):
            print(f"    - {func}")
        total += len(funcs)

    if inventory.classes:
        print(f"\n  导出类 ({len(inventory.classes)} 个类):")
        for cls in inventory.classes:
            print(f"    - {cls}")

    return total


def _verbose_module_summary(module_name: str, inventory: ModuleInventory) -> None:
    categorized = categorize_module(module_name, inventory.functions)
    print(f"  {inventory.display_name} 模块:")
    for category, funcs in categorized.items():
        print(f"    {category}: {len(funcs)} 个函数")
        for func in funcs[:3]:
            print(f"      - {func}")
        if len(funcs) > 3:
            print(f"      ... 和其他 {len(funcs) - 3} 个函数")
    if inventory.classes:
        print(f"    导出类: {len(inventory.classes)} 个")


def _target_symbols(inventory: Dict[str, ModuleInventory]) -> List[str]:
    symbols: List[str] = []
    for module_name in ("operations", "evolve", "constraints"):
        symbols.extend(inventory[module_name].functions)
        symbols.extend(inventory[module_name].classes)
    symbols.extend(["field", "ql"])
    return symbols


def main() -> None:
    args = parse_arguments()

    if args.verbose:
        print("🚀 开始更新 __init__.py 文件...")
        print(f"📦 包目录: {PACKAGE_ROOT}")

    inventory = collect_api_inventory()
    operations_functions = inventory["operations"].functions
    evolve_functions = inventory["evolve"].functions

    if not any(item.functions or item.classes for item in inventory.values()):
        print("❌ 未找到任何公共 API，退出")
        return

    target_symbols = _target_symbols(inventory)
    new_additions, removed_functions = compare_with_existing(target_symbols)

    if args.verbose:
        print("\n📊 函数分类统计:")
        for module_name in MODULE_ORDER:
            _verbose_module_summary(module_name, inventory[module_name])

    if new_additions and args.verbose:
        print(f"\n🆕 新增导出 ({len(new_additions)} 个):")
        for name in new_additions:
            print(f"  + {name}")

    if removed_functions and args.verbose:
        print(f"\n🗑️  删除导出 ({len(removed_functions)} 个):")
        for name in removed_functions:
            print(f"  - {name}")

    if args.show_api_only:
        print("\n📜 API 函数列表 (按模块和类别分组):")
        totals: Dict[str, int] = {}
        for module_name in MODULE_ORDER:
            totals[module_name] = _print_module_summary(
                module_name, inventory[module_name]
            )

        print(
            "\n📊 总计: "
            f"Operations {totals['operations']} 个函数, "
            f"Evolve {totals['evolve']} 个函数, "
            f"Constraints {totals['constraints']} 个函数, "
            f"Field {totals['field']} 个函数, "
            f"QL {totals['ql']} 个函数, "
            f"总计 {sum(totals.values())} 个函数"
        )
        return

    new_content = generate_init_file(inventory)

    if args.dry_run:
        print("\n👁️  预览模式 - 将要进行的更改:")
        print(f"  生成的文件大小: {len(new_content)} 字符")
        print(f"  Operations 函数数: {len(operations_functions)}")
        print(f"  Evolve 函数数: {len(evolve_functions)}")
        print(f"  Constraints 函数数: {len(inventory['constraints'].functions)}")
        print(f"  Field 函数数: {len(inventory['field'].functions)}")
        print(f"  QL 函数数: {len(inventory['ql'].functions)}")
        print(f"  总导出符号数: {len(target_symbols)}")
        print(
            f"  别名数: {len([name for name in operations_functions + evolve_functions if name in ALIAS_RULES])}"
        )
        print("  (使用 --verbose 查看详细信息)")
        print("\n💡 要实际执行更改，请移除 --dry-run 参数")
        return

    if args.backup:
        backup_init_file()

    print("\n🔄 生成新的 __init__.py 文件...")
    INIT_FILE.write_text(new_content, encoding="utf-8")

    print("🔍 检查生成文件的语法...")
    if not check_syntax(INIT_FILE):
        print("❌ 语法检查失败，请检查生成的文件")
        return

    print("✅ 语法检查通过")
    print(f"✅ 已更新 {INIT_FILE}")
    print("🎉 更新完成！")

    print("\n📈 统计信息:")
    for module_name in MODULE_ORDER:
        print(
            f"  {MODULE_LABELS[module_name]} 函数数: {len(inventory[module_name].functions)}"
        )
    print(f"  Constraints 类数: {len(inventory['constraints'].classes)}")
    print(f"  总导出符号数: {len(target_symbols)}")
    print(
        f"  别名数: {len([name for name in operations_functions + evolve_functions if name in ALIAS_RULES])}"
    )

    print("\n💡 建议:")
    print(f"  1. 检查生成的 {INIT_FILE} 文件")
    print("  2. 运行测试确保所有导入正常工作")
    if args.backup:
        print(f"  3. 如有问题，可以从备份文件 {INIT_FILE}.bak 恢复")


if __name__ == "__main__":
    main()
