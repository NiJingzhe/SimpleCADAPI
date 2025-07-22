#!/usr/bin/env python3
"""
自动文档生成脚本
从operations.py中提取所有API并生成格式统一的markdown文档
"""

import ast
import os
from typing import List, Dict, Optional
import sys

# 添加src目录到路径以便导入模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    from simplecadapi import operations
except ImportError as e:
    print(f"无法导入operations模块: {e}")
    sys.exit(1)


class APIDocumentGenerator:
    """API文档生成器"""

    def __init__(self, operations_file_path: str, output_dir: str = "docs"):
        self.operations_file_path = operations_file_path
        self.output_dir = output_dir
        self.apis = []

        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def extract_apis(self) -> List[Dict]:
        """从operations.py文件中提取所有API信息"""
        print("正在分析operations.py文件...")

        # 读取源代码文件
        with open(self.operations_file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        # 解析AST
        tree = ast.parse(source_code)

        # 提取所有函数定义
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # 跳过私有函数
                if node.name.startswith("_"):
                    continue

                api_info = self._extract_function_info(node, source_code)
                if api_info:
                    self.apis.append(api_info)

        print(f"成功提取到 {len(self.apis)} 个API")
        return self.apis

    def _extract_function_info(
        self, node: ast.FunctionDef, source_code: str
    ) -> Optional[Dict]:
        """提取单个函数的信息"""
        try:
            # 获取函数名
            func_name = node.name

            # 获取函数签名
            signature = self._get_function_signature(node)

            # 获取docstring
            docstring = ast.get_docstring(node)
            if not docstring:
                return None

            # 解析docstring
            parsed_doc = self._parse_docstring(docstring)

            return {
                "name": func_name,
                "signature": signature,
                "docstring": docstring,
                "parsed_doc": parsed_doc,
            }
        except Exception as e:
            print(f"提取函数 {node.name} 信息时出错: {e}")
            return None

    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """获取函数签名"""
        # 构建参数列表
        args = []

        # 处理普通参数
        for arg in node.args.args:
            arg_str = arg.arg
            # 添加类型注解
            if arg.annotation:
                arg_str += f": {ast.unparse(arg.annotation)}"
            args.append(arg_str)

        # 处理默认参数
        defaults = node.args.defaults
        if defaults:
            # 为有默认值的参数添加默认值
            num_defaults = len(defaults)
            for i, default in enumerate(defaults):
                arg_index = len(args) - num_defaults + i
                if arg_index < len(args):
                    args[arg_index] += f" = {ast.unparse(default)}"

        # 构建返回类型
        return_type = ""
        if node.returns:
            return_type = f" -> {ast.unparse(node.returns)}"

        return f"def {node.name}({', '.join(args)}){return_type}"

    def _parse_docstring(self, docstring: str) -> Dict:
        """解析docstring，提取各个部分"""
        parsed = {
            "description": "",
            "args": [],
            "returns": "",
            "raises": [],
            "usage": "",
            "examples": [],
        }

        lines = docstring.split("\n")
        current_section = "description"
        current_content = []

        for line in lines:
            line = line.strip()

            # 检查是否是新的段落
            if line in ["Args:", "Returns:", "Raises:", "Usage:", "Example:"]:
                # 保存当前段落内容
                if current_content:
                    self._add_section_content(parsed, current_section, current_content)
                    current_content = []

                # 切换到新段落
                current_section = line.rstrip(":").lower()
                continue

            # 添加内容到当前段落
            if line:
                current_content.append(line)

        # 处理最后一个段落
        if current_content:
            self._add_section_content(parsed, current_section, current_content)

        return parsed

    def _add_section_content(self, parsed: Dict, section: str, content: List[str]):
        """添加段落内容到解析结果"""
        content_str = "\n".join(content)

        if section == "description":
            parsed["description"] = content_str
        elif section == "args":
            parsed["args"] = self._parse_args_section(content)
        elif section == "returns":
            parsed["returns"] = content_str
        elif section == "raises":
            parsed["raises"] = self._parse_raises_section(content)
        elif section == "usage":
            parsed["usage"] = content_str
        elif section == "example":
            parsed["examples"] = self._parse_examples_section(content)

    def _parse_args_section(self, content: List[str]) -> List[Dict]:
        """解析Args段落"""
        args = []
        current_arg = None

        for line in content:
            # 检查是否是参数定义行
            if ":" in line and not line.startswith("    "):
                # 保存之前的参数
                if current_arg:
                    args.append(current_arg)

                # 解析新参数
                parts = line.split(":", 1)
                if len(parts) == 2:
                    param_info = parts[0].strip()
                    description = parts[1].strip()

                    # 解析参数名和类型
                    if "(" in param_info and ")" in param_info:
                        name = param_info[: param_info.index("(")].strip()
                        type_info = param_info[
                            param_info.index("(") + 1 : param_info.rindex(")")
                        ].strip()
                    else:
                        name = param_info
                        type_info = ""

                    current_arg = {
                        "name": name,
                        "type": type_info,
                        "description": description,
                    }
            else:
                # 添加到当前参数的描述
                if current_arg and line.strip():
                    current_arg["description"] += " " + line.strip()

        # 添加最后一个参数
        if current_arg:
            args.append(current_arg)

        return args

    def _parse_raises_section(self, content: List[str]) -> List[Dict]:
        """解析Raises段落"""
        raises = []

        for line in content:
            if ":" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    exception_type = parts[0].strip()
                    description = parts[1].strip()
                    raises.append({"type": exception_type, "description": description})

        return raises

    def _parse_examples_section(self, content: List[str]) -> List[str]:
        """解析Examples段落"""
        examples = []
        current_example = []
        in_example_block = False

        for line in content:
            # 检测新的例子开始（以注释开始）
            if line.startswith(" #"):
                # 保存之前的例子
                if current_example:
                    examples.append("\n".join(current_example))
                    current_example = []
                # 开始新的例子
                current_example.append(line)
                in_example_block = True
            elif line.startswith(" ") or line.startswith("... "):
                # 继续当前例子
                current_example.append(line)
                in_example_block = True
            elif line.strip() == "" and in_example_block:
                # 空行，但在例子块中
                current_example.append(line)
            elif (
                line.strip() != ""
                and not line.startswith(" ")
                and not line.startswith("... ")
            ):
                # 非代码行，可能是例子结束
                if in_example_block and current_example:
                    examples.append("\n".join(current_example))
                    current_example = []
                    in_example_block = False

        # 添加最后一个例子
        if current_example:
            examples.append("\n".join(current_example))

        return examples

    def generate_markdown_docs(self):
        """生成markdown文档"""
        print("正在生成markdown文档...")

        for api in self.apis:
            self._generate_single_api_doc(api)

        # 生成API索引文档
        self._generate_api_index()

        print(f"文档生成完成！输出目录: {self.output_dir}")

    def _generate_single_api_doc(self, api: Dict):
        """生成单个API的markdown文档"""
        name = api["name"]
        signature = api["signature"]
        parsed_doc = api["parsed_doc"]

        # 创建markdown内容
        md_content = []

        # 1. API定义
        md_content.append(f"# {name}")
        md_content.append("")
        md_content.append("## API定义")
        md_content.append("")
        md_content.append("```python")
        md_content.append(signature)
        md_content.append("```")
        md_content.append("")

        # 2. API作用
        if parsed_doc["usage"]:
            md_content.append("## API作用")
            md_content.append("")
            md_content.append(parsed_doc["usage"])
            md_content.append("")

        # 3. API参数说明
        if parsed_doc["args"]:
            md_content.append("## API参数说明")
            md_content.append("")
            for arg in parsed_doc["args"]:
                md_content.append(f"### {arg['name']}")
                md_content.append("")
                if arg["type"]:
                    md_content.append(f"- **类型**: `{arg['type']}`")
                md_content.append(f"- **说明**: {arg['description']}")
                md_content.append("")

        # 4. 返回值说明
        if parsed_doc["returns"]:
            md_content.append("### 返回值")
            md_content.append("")
            md_content.append(parsed_doc["returns"])
            md_content.append("")

        # 5. 异常说明
        if parsed_doc["raises"]:
            md_content.append("## 异常")
            md_content.append("")
            for exc in parsed_doc["raises"]:
                md_content.append(f"- **{exc['type']}**: {exc['description']}")
            md_content.append("")

        # 6. API使用例子
        if parsed_doc["examples"]:
            md_content.append("## API使用例子")
            md_content.append("")
            md_content.append("```python")
            # 将所有例子合并到一个代码块中
            all_examples = "\n\n".join(parsed_doc["examples"])
            md_content.append(all_examples)
            md_content.append("```")
            md_content.append("")

        # 写入文件
        filename = f"{name}.md"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))

        print(f"  生成文档: {filename}")

    def _generate_api_index(self):
        """生成API索引文档"""
        md_content = []

        md_content.append("# SimpleCAD API 文档索引")
        md_content.append("")
        md_content.append("本文档包含了 SimpleCAD API 的所有函数说明。")
        md_content.append("")

        # 按功能分类
        categories = {
            "基础图形创建": [],
            "变换操作": [],
            "3D操作": [],
            "标签和选择": [],
            "布尔运算": [],
            "导出功能": [],
            "高级特征": [],
            "其他": [],
        }

        for api in self.apis:
            name = api["name"]

            # 根据函数名前缀分类
            if name.startswith("make_"):
                categories["基础图形创建"].append(name)
            elif name.startswith(("translate_", "rotate_", "mirror_")):
                categories["变换操作"].append(name)
            elif name.startswith(("extrude_", "revolve_", "loft_", "sweep_")):
                categories["3D操作"].append(name)
            elif name.startswith(("set_tag", "select_")):
                categories["标签和选择"].append(name)
            elif name.startswith(("union_", "cut_", "intersect_")):
                categories["布尔运算"].append(name)
            elif name.startswith("export_"):
                categories["导出功能"].append(name)
            elif name.startswith(
                ("fillet_", "chamfer_", "shell_", "pattern_", "helical_")
            ):
                categories["高级特征"].append(name)
            else:
                categories["其他"].append(name)

        # 生成分类索引
        for category, functions in categories.items():
            if functions:
                md_content.append(f"## {category}")
                md_content.append("")
                for func in sorted(functions):
                    md_content.append(f"- [{func}]({func}.md)")
                md_content.append("")

        # 写入索引文件
        with open(
            os.path.join(self.output_dir, "README.md"), "w", encoding="utf-8"
        ) as f:
            f.write("\n".join(md_content))

        print("  生成索引文档: README.md")


def main():
    """主函数"""
    # 获取operations.py文件路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    operations_file = os.path.join(
        script_dir, "..", "src", "simplecadapi", "operations.py"
    )

    if not os.path.exists(operations_file):
        print(f"错误：找不到operations.py文件: {operations_file}")
        return

    # 创建输出目录
    output_dir = os.path.join(script_dir, "..", "docs", "api")

    # 创建文档生成器
    generator = APIDocumentGenerator(operations_file, output_dir)

    # 提取API信息
    apis = generator.extract_apis()

    if not apis:
        print("没有找到任何API函数")
        return

    # 生成文档
    generator.generate_markdown_docs()

    print(f"\n✅ 文档生成完成！")
    print(f"📁 输出目录: {output_dir}")
    print(f"📄 生成了 {len(apis)} 个API文档")
    print(f"📋 索引文件: {os.path.join(output_dir, 'README.md')}")


if __name__ == "__main__":
    main()

