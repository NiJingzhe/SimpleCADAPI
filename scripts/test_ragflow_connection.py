#!/usr/bin/env python3
"""
RAGFlow连接测试脚本
用于验证RAGFlow连接和API密钥是否正常工作
"""

import os
import sys
from pathlib import Path

# 添加脚本目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

try:
    from ragflow_sdk import RAGFlow
except ImportError:
    print("❌ 错误: 未安装ragflow-sdk")
    print("请运行: pip install ragflow-sdk")
    exit(1)

def test_ragflow_connection():
    """测试RAGFlow连接"""
    
    # 获取环境变量
    API_KEY = os.getenv("RAGFLOW_API_KEY", "")
    BASE_URL = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")
    
    if not API_KEY:
        print("❌ 错误: 未设置RAGFLOW_API_KEY环境变量")
        print("请运行: export RAGFLOW_API_KEY='your_api_key_here'")
        return False
    
    print(f"🔧 测试RAGFlow连接...")
    print(f"   服务器地址: {BASE_URL}")
    print(f"   API密钥: {API_KEY[:10]}...")
    
    try:
        # 创建RAGFlow客户端
        rag_client = RAGFlow(api_key=API_KEY, base_url=BASE_URL)
        
        # 测试连接 - 尝试获取数据集列表
        print("📋 获取数据集列表...")
        datasets = rag_client.list_datasets()
        
        print(f"✅ 连接成功!")
        print(f"   找到 {len(datasets)} 个数据集")
        
        # 显示现有数据集
        if datasets:
            print("\n📚 现有数据集:")
            for i, dataset in enumerate(datasets, 1):
                print(f"   {i}. {dataset.name}")
        
        # 检查是否存在SimpleCADAPI数据集
        simpleapi_datasets = [d for d in datasets if d.name == "SimpleCADAPI"]
        if simpleapi_datasets:
            print(f"\n🎯 找到SimpleCADAPI数据集")
            dataset = simpleapi_datasets[0]
            
            # 获取文档数量
            try:
                docs = dataset.list_documents()
                print(f"   包含 {len(docs)} 个文档")
                
                # 统计总分块数
                total_chunks = 0
                for doc in docs[:3]:  # 只检查前3个文档以节省时间
                    try:
                        chunks = doc.list_chunks()
                        total_chunks += len(chunks)
                    except:
                        pass
                
                if total_chunks > 0:
                    print(f"   前3个文档包含 {total_chunks} 个分块")
                    
            except Exception as e:
                print(f"   ⚠️  获取文档信息失败: {e}")
        else:
            print(f"\n📝 未找到SimpleCADAPI数据集，首次运行同步脚本时会自动创建")
        
        return True
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("\n💡 可能的解决方案:")
        print("   1. 检查RAGFlow服务器是否正在运行")
        print("   2. 验证BASE_URL是否正确")
        print("   3. 确认API_KEY是否有效")
        print("   4. 检查网络连接")
        return False

def main():
    """主函数"""
    print("🚀 RAGFlow连接测试")
    print("=" * 50)
    
    success = test_ragflow_connection()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ 测试通过! 可以运行同步脚本了")
        print("运行命令: python scripts/ragflow_sync.py")
    else:
        print("❌ 测试失败! 请检查配置后重试")
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main())
