#!/bin/bash

# RAGFlow同步脚本环境配置示例
# 复制此文件为 .env 并根据实际情况修改

# RAGFlow API密钥 (必须设置)
export RAGFLOW_API_KEY="ragflow-c3YzI1YTk0NTY0ODExZjBiNDZjYmExNm"

# RAGFlow服务器地址 (可选，默认为localhost:9380)
export RAGFLOW_BASE_URL="http://localhost:9380"

# 数据集名称 (在脚本中可修改)
# DATASET_NAME="SimpleCADAPI"

echo "RAGFlow环境变量已设置"
echo "API Key: ${RAGFLOW_API_KEY:0:10}..."
echo "Base URL: $RAGFLOW_BASE_URL"
