#!/bin/bash
# SimpleCAD API 发布脚本

# 请在运行脚本前设置环境变量：
# export TWINE_USERNAME=__token__
# export TWINE_PASSWORD=your-pypi-token-here

# 检查是否设置了必要的环境变量
if [ -z "$TWINE_USERNAME" ] || [ -z "$TWINE_PASSWORD" ]; then
    echo "❌ 错误：请先设置 PyPI 认证信息："
    echo "export TWINE_USERNAME=__token__"
    echo "export TWINE_PASSWORD=your-pypi-token-here"
    exit 1
fi

set -e  # 遇到错误立即退出

echo "🚀 开始发布 SimpleCAD API..."

# 清理旧的构建文件
echo "🧹 清理旧的构建文件..."
rm -rf dist/ build/ *.egg-info/

# 构建包
echo "📦 构建包..."
uv build

# 检查构建的包
echo "🔍 检查构建的包..."
uv run twine check dist/*

# 确认发布
read -p "确认发布到正式 PyPI？(y/N): " confirm
if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo "❌ 发布已取消"
    exit 0
fi

# 发布到正式 PyPI
echo "🌟 发布到正式 PyPI..."
uv run twine upload dist/*

echo "🎉 发布完成！"
echo "📦 包地址: https://pypi.org/project/simplecadapi/"
echo "📋 安装命令: pip install simplecadapi"