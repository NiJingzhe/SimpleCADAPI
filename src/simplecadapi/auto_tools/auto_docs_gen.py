#!/usr/bin/env python3
"""
自动文档生成脚本
从operations.py和evolve.py中提取所有API并生成格式统一的markdown文档
"""
import ast
import os
from typing import List, Dict, Optional
import sys

# 添加src目录到路径以便导入模块
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 尝试导入模块（虽然此脚本主要通过AST解析，但导入可以用于验证）
try:
    from simplecadapi import operations, evolve
except ImportError as e:
    # print(f"警告: 无法导入模块: {e}") # 不强制要求能导入，只要文件存在即可
    pass


class APIDocumentGenerator:
    """API文档生成器"""

    def __init__(self, source_files: List[str], output_dir: str = "docs"):
        self.source_files = source_files  # List of file paths to process
        self.output_dir = output_dir
        self.apis: List[Dict] = []  # Store all extracted APIs
        # 创建输出目录
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

    def extract_apis(self) -> List[Dict]:
        """从指定的源文件列表中提取所有API信息"""
        print("正在分析源文件...")
        total_apis = 0
        for file_path in self.source_files:
            if not os.path.exists(file_path):
                print(f"警告: 找不到文件 {file_path}，跳过。")
                continue

            print(f"  正在处理 {file_path}...")
            # 读取源代码文件
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    source_code = f.read()
            except Exception as e:
                print(f"读取文件 {file_path} 时出错: {e}")
                continue

            # 解析AST
            try:
                tree = ast.parse(source_code)
            except SyntaxError as e:
                print(f"解析文件 {file_path} 时出现语法错误: {e}")
                continue

            # 提取所有函数定义
            file_apis = 0
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    # 跳过私有函数
                    if node.name.startswith("_"):
                        continue
                    api_info = self._extract_function_info(node, source_code, file_path)
                    if api_info:
                        self.apis.append(api_info)
                        file_apis += 1
            print(f"    从 {os.path.basename(file_path)} 提取到 {file_apis} 个API")
            total_apis += file_apis

        print(f"成功总共提取到 {total_apis} 个API")
        return self.apis

    def _extract_function_info(
        self, node: ast.FunctionDef, source_code: str, file_path: str
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
                # print(f"  警告: 函数 {func_name} 没有docstring，跳过。") # 可选：警告无docstring的函数
                return None
            # 解析docstring
            parsed_doc = self._parse_docstring(docstring)
            return {
                "name": func_name,
                "signature": signature,
                "docstring": docstring,
                "parsed_doc": parsed_doc,
                "source_file": os.path.basename(file_path),  # 记录来源文件
            }
        except Exception as e:
            print(f"提取函数 {node.name} (来自 {file_path}) 信息时出错: {e}")
            return None

    def _get_function_signature(self, node: ast.FunctionDef) -> str:
        """获取函数签名"""
        # 构建参数列表
        args = []
        # 处理普通参数
        for arg in node.args.args:
            arg_str = arg.arg
            # 添加类型注解 (使用 ast.unparse if available, otherwise basic)
            try:
                if arg.annotation:
                    arg_str += f": {ast.unparse(arg.annotation)}"
            except (AttributeError, Exception):
                # Fallback for older Python versions or issues
                if arg.annotation:
                    arg_str += f": {ast.dump(arg.annotation)}"  # 或者简单地用占位符
            args.append(arg_str)

        # 处理默认参数
        defaults = node.args.defaults
        if defaults:
            # 为有默认值的参数添加默认值
            num_defaults = len(defaults)
            for i, default in enumerate(defaults):
                arg_index = len(args) - num_defaults + i
                if arg_index < len(args):
                    try:
                        args[arg_index] += f" = {ast.unparse(default)}"
                    except (AttributeError, Exception):
                        # Fallback for older Python versions or issues
                        args[arg_index] += f" = ..."  # 或者简单地用占位符

        # 构建返回类型
        return_type = ""
        if node.returns:
            try:
                return_type = f" -> {ast.unparse(node.returns)}"
            except (AttributeError, Exception):
                # Fallback for older Python versions or issues
                return_type = f" -> ..."  # 或者简单地用占位符

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
        lines = docstring.split("\n")  # 修正：使用 \n 分割
        current_section = "description"
        current_content: List[str] = []
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
        content_str = "\n".join(content)  # 修正：用 \n 连接
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
            # 检查是否是参数定义行 (更健壮的检查)
            # 假设格式是 `param_name (type): description` 或 `param_name: description`
            # 避免将缩进的描述行误认为是新参数
            if ":" in line and not line.startswith((" ", "\t")):
                # 保存之前的参数
                if current_arg:
                    args.append(current_arg)
                # 解析新参数
                # 找到第一个冒号的位置
                colon_idx = line.find(":")
                param_info = line[:colon_idx].strip()
                description = line[colon_idx + 1 :].strip()

                # 解析参数名和类型
                name = param_info
                type_info = ""
                if "(" in param_info and ")" in param_info and param_info.endswith(")"):
                    # 查找最后一个 ( 和 )
                    last_open = param_info.rfind("(")
                    last_close = param_info.rfind(")")
                    if last_open < last_close:  # 确保顺序正确
                        name = param_info[:last_open].strip()
                        type_info = param_info[last_open + 1 : last_close].strip()

                current_arg = {
                    "name": name,
                    "type": type_info,
                    "description": description,
                }
            else:
                # 添加到当前参数的描述 (处理换行)
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
            # 同样，避免将缩进行误认为是新异常
            if ":" in line and not line.startswith((" ", "\t")):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    exception_type = parts[0].strip()
                    description = parts[1].strip()
                    raises.append({"type": exception_type, "description": description})
                # 处理多行描述的情况（如果需要）
                # 此处简单处理，假设每行都是独立的异常定义
        return raises

    def _parse_examples_section(self, content: List[str]) -> List[str]:
        """解析Examples段落"""
        # 原逻辑较复杂，简化为按空行分隔例子块
        examples = []
        current_block: List[str] = []
        for line in content:
            if line.strip() == "":
                if current_block:
                    examples.append("\n".join(current_block))
                    current_block = []
            else:
                current_block.append(line)
        if current_block:  # Add the last block
            examples.append("\n".join(current_block))

        return examples

    def generate_markdown_docs(self):
        """生成markdown文档"""
        print("正在生成markdown文档...")
        generated_count = 0
        for api in self.apis:
            try:
                self._generate_single_api_doc(api)
                generated_count += 1
            except Exception as e:
                print(f"生成文档 {api['name']}.md 时出错: {e}")
        # 生成API索引文档
        try:
            self._generate_api_index()
        except Exception as e:
            print(f"生成索引文档 README.md 时出错: {e}")
        print(
            f"文档生成完成！输出目录: {self.output_dir} (成功生成 {generated_count} 个API文档)"
        )

    def _generate_single_api_doc(self, api: Dict):
        """生成单个API的markdown文档"""
        name = api["name"]
        signature = api["signature"]
        parsed_doc = api["parsed_doc"]
        source_file = api.get("source_file", "Unknown")
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
        md_content.append(f"*来源文件: {source_file}*")  # 添加来源信息
        md_content.append("")
        # 2. API作用 / Usage
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
            md_content.append("## 返回值说明")
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
            for i, example_block in enumerate(parsed_doc["examples"]):
                if len(parsed_doc["examples"]) > 1:
                    md_content.append(f"### 例子 {i+1}")
                md_content.append("```python")
                md_content.append(example_block)
                md_content.append("```")
                md_content.append("")

        # 写入文件
        filename = f"{name}.md"
        filepath = os.path.join(self.output_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))  # 用 \n 连接
        # print(f"  生成文档: {filename}") # 可在 extract_apis 中打印

    def _generate_api_index(self):
        """生成API索引文档"""
        md_content = []
        md_content.append("# SimpleCAD API 文档索引")
        md_content.append("")
        md_content.append(
            "本文档包含了 SimpleCAD API (来自 `operations.py` 和 `evolve.py`) 的所有函数说明。"
        )
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
            "自进化": [],  # 新增的分类
            "其他": [],
        }

        # 分类逻辑
        for api in self.apis:
            name = api["name"]
            source_file = api.get("source_file", "")

            # 首先检查是否来自evolve.py，如果是则归入“自进化”
            if source_file == "evolve.py":
                categories["自进化"].append(api)
                continue  # 处理完后跳过后续分类

            # 否则，按原有规则对operations.py中的API进行分类
            categorized = False
            if name.startswith("make_"):
                categories["基础图形创建"].append(api)
                categorized = True
            elif name.startswith(("translate_", "rotate_", "mirror_")):
                categories["变换操作"].append(api)
                categorized = True
            elif name.startswith(("extrude_", "revolve_", "loft_", "sweep_")):
                categories["3D操作"].append(api)
                categorized = True
            elif name.startswith(("set_tag", "select_")):
                categories["标签和选择"].append(api)
                categorized = True
            elif name.startswith(("union_", "cut_", "intersect_")):
                categories["布尔运算"].append(api)
                categorized = True
            elif name.startswith("export_"):
                categories["导出功能"].append(api)
                categorized = True
            elif name.startswith(
                ("fillet_", "chamfer_", "shell_", "pattern_", "helical_")
            ):
                categories["高级特征"].append(api)
                categorized = True

            if not categorized:
                categories["其他"].append(api)  # 添加到未分类列表

        # 生成分类索引
        for category, api_list in categories.items():
            if api_list:
                md_content.append(f"## {category}")
                md_content.append("")
                # 按名称排序
                sorted_apis = sorted(api_list, key=lambda x: x["name"])
                for api in sorted_apis:
                    # 在索引中也显示来源文件
                    source_info = f" *(来自 {api['source_file']})*"
                    md_content.append(
                        f"- [{api['name']}]({api['name']}.md){source_info}"
                    )
                md_content.append("")

        # 写入索引文件
        index_path = os.path.join(self.output_dir, "README.md")
        with open(index_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md_content))  # 用 \n 连接
        print("  生成索引文档: README.md")


def main():
    """主函数"""
    # 获取脚本目录
    script_dir = os.path.dirname(os.path.abspath(__file__))

    # 定义要处理的源文件列表
    source_files = [
        os.path.join(script_dir, "..", "operations.py"),
        os.path.join(script_dir, "..", "evolve.py"),
    ]

    # 检查文件是否存在
    existing_files = [f for f in source_files if os.path.exists(f)]
    if not existing_files:
        print(f"错误：找不到任何指定的源文件: {source_files}")
        return

    # 创建输出目录
    output_dir = os.path.join(script_dir, "..", "..", "docs", "api")

    # 创建文档生成器
    generator = APIDocumentGenerator(existing_files, output_dir)

    # 提取API信息
    apis = generator.extract_apis()
    if not apis:
        print("没有找到任何带有docstring的API函数")
        return

    # 生成文档
    generator.generate_markdown_docs()

    print(f"\n✅ 文档生成完成！")
    print(f"📁 输出目录: {output_dir}")
    print(
        f"📄 生成了 {len([a for a in apis if a.get('parsed_doc')])} 个API文档"
    )  # 更准确地计算
    print(f"📋 索引文件: {os.path.join(output_dir, 'README.md')}")


if __name__ == "__main__":
    main()
