#!/usr/bin/env python3
"""
RAGFlow数据库同步脚本
自动同步SimpleCADAPI文档到RAGFlow数据库
"""

import os
import hashlib
import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
import re

from ragflow_sdk import RAGFlow, Document, Chunk, DataSet

class SimpleCADAPIRAGFlowSync:
    def __init__(self, api_key: str, base_url: str, dataset_name: str = "SimpleCADAPI"):
        """
        初始化RAGFlow同步器
        
        Args:
            api_key: RAGFlow API密钥
            base_url: RAGFlow服务器地址
            dataset_name: 数据集名称
        """
        self.api_key = api_key
        self.base_url = base_url
        self.dataset_name = dataset_name
        self.rag_client = RAGFlow(api_key=api_key, base_url=base_url)
        self.dataset: Optional[DataSet] = None
        self.docs_dir = Path(__file__).parent.parent / "docs"
        self.cache_file = Path(__file__).parent / "ragflow_cache.json"
        self.file_hashes = self._load_cache()
        
    def _load_cache(self) -> Dict[str, str]:
        """加载文件哈希缓存"""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_cache(self):
        """保存文件哈希缓存"""
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            json.dump(self.file_hashes, f, indent=2, ensure_ascii=False)
    
    def _get_file_hash(self, filepath: Path) -> str:
        """获取文件的MD5哈希值"""
        with open(filepath, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    
    def _ensure_dataset(self):
        """确保数据集存在，如果不存在则创建"""
        try:
            # 获取所有数据集
            print("获取数据集列表...")
            all_datasets = self.rag_client.list_datasets()
            
            # 查找匹配的数据集
            matching_datasets = [d for d in all_datasets if d.name == self.dataset_name]
            
            if matching_datasets:
                self.dataset = matching_datasets[0]
                print(f"找到已存在的数据集: {self.dataset_name}")
            else:
                # 创建新数据集
                print(f"创建新数据集: {self.dataset_name}")
                self.dataset = self.rag_client.create_dataset(
                    name=self.dataset_name,
                    description="SimpleCADAPI文档数据集，包含所有API和核心概念文档",
                    chunk_method="manual"  # 使用手动分块模式
                )
                print(f"成功创建数据集: {self.dataset_name}")
                
        except Exception as e:
            print(f"处理数据集时出错: {e}")
            # 尝试直接创建数据集
            print(f"尝试直接创建数据集: {self.dataset_name}")
            try:
                self.dataset = self.rag_client.create_dataset(
                    name=self.dataset_name,
                    description="SimpleCADAPI文档数据集，包含所有API和核心概念文档",
                    chunk_method="manual"  # 使用手动分块模式
                )
                print(f"成功创建数据集: {self.dataset_name}")
            except Exception as create_error:
                print(f"创建数据集失败: {create_error}")
                raise
    
    def _split_markdown_by_h2(self, content: str, filename: str) -> List[Dict[str, str]]:
        """
        按照二级标题(##)分割markdown文档
        
        Args:
            content: markdown文档内容
            filename: 文件名
            
        Returns:
            包含分块信息的字典列表
        """
        chunks = []
        
        # 确保输入参数不为 None
        if content is None:
            content = ''
        if filename is None:
            filename = 'unknown'
        
        lines = content.split('\n')
        current_chunk = []
        current_title = ""
        
        for line in lines:
            # 检查是否为二级标题
            if line.startswith('## '):
                # 如果已有内容，保存上一个块
                if current_chunk:
                    chunk_content = '\n'.join(current_chunk).strip()
                    if chunk_content:
                        chunks.append({
                            'title': current_title or f"Section {len(chunks) + 1}",
                            'content': chunk_content,
                            'filename': filename
                        })
                
                # 开始新块
                current_title = line[3:].strip()  # 去掉'## '
                current_chunk = [line]
            else:
                current_chunk.append(line)
        
        # 添加最后一个块
        if current_chunk:
            chunk_content = '\n'.join(current_chunk).strip()
            if chunk_content:
                chunks.append({
                    'title': current_title or f"Section {len(chunks) + 1}",
                    'content': chunk_content,
                    'filename': filename
                })
        
        # 如果没有找到二级标题，将整个文档作为一个块
        if not chunks:
            chunks.append({
                'title': filename,
                'content': content.strip(),
                'filename': filename
            })
        
        return chunks
    
    def _get_all_markdown_files(self) -> List[Path]:
        """获取所有markdown文件"""
        md_files = []
        for pattern in ["**/*.md"]:
            md_files.extend(self.docs_dir.glob(pattern))
        return md_files
    
    def _find_document_by_name(self, doc_name: str) -> Optional[Document]:
        """根据文档名称查找文档"""
        assert self.dataset is not None, "数据集未初始化，请先调用 _ensure_dataset()"
        docs = self.dataset.list_documents()
        for doc in docs:
            if doc.name == doc_name:
                return doc
        return None
    
    def _update_document_with_chunks(self, doc_name: str, chunks: List[Dict[str, str]]):
        """使用分块更新文档"""
        assert self.dataset is not None, "数据集未初始化，请先调用 _ensure_dataset()"
        print(f"  处理文档: {doc_name}")
        
        # 查找现有文档
        existing_doc: Optional[Document] = self._find_document_by_name(doc_name)
        
        if existing_doc:
            print(f"  删除现有文档: {doc_name}")
            # 删除现有文档
            self.dataset.delete_documents([existing_doc.id])
            time.sleep(1)  # 等待删除完成
        
        # 创建新文档（使用空内容）
        print(f"  创建新文档: {doc_name}")
        self.dataset.upload_documents([{
            "display_name": doc_name,
            "blob": b"# Document Content\n\nThis document contains API documentation."
        }])
        
        # 等待文档创建完成
        time.sleep(2)
        
        # 获取新创建的文档
        new_doc: Optional[Document] = self._find_document_by_name(doc_name)
        if not new_doc:
            print(f"  错误: 无法找到新创建的文档 {doc_name}")
            return
        
        # 删除默认的chunks
        existing_chunks = new_doc.list_chunks()
        if existing_chunks:
            chunk_ids = [chunk.id for chunk in existing_chunks]
            new_doc.delete_chunks(chunk_ids)
            time.sleep(1)
        
        # 添加新的chunks
        print(f"  添加 {len(chunks)} 个分块")
        for i, chunk in enumerate(chunks):
            title = chunk.get('title', '') or ''
            content = chunk.get('content', '') or ''
            
            # 确保 title 和 content 不为 None
            if title is None:
                title = ''
            if content is None:
                content = ''
            
            # 创建分块标题和内容
            chunk_title = f"{title}" if title else f"Section {i+1}"
            
            # 提取重要关键词
            keywords = self._extract_keywords(content, chunk_title, doc_name)
            
            # 确保 keywords 不为 None 且不包含 None 值
            if keywords is None:
                keywords = []
            keywords = [k for k in keywords if k is not None and k.strip()]
            keywords_str = ', '.join(keywords) if keywords else ''
            
            try:
                # 简化内容格式，避免特殊字符问题
                clean_content = content.strip()
                if not clean_content:
                    clean_content = f"Empty content for section: {chunk_title}"
                
                # 创建简单的内容格式
                final_content = f"# {chunk_title}\n\n{clean_content}\n\n# tags: {keywords_str}\n\n"
                
                # 确保关键词都是有效的字符串
                clean_keywords = []
                for kw in keywords:
                    if kw and isinstance(kw, str) and len(kw.strip()) > 0:
                        clean_keywords.append(kw.strip())
                
                print(f"    添加分块: {chunk_title}")
                print(f"    内容长度: {len(final_content)}, 关键词: {clean_keywords}")
                
                # 使用简单的方法调用
                new_doc.add_chunk(
                    content=final_content,
                    important_keywords=clean_keywords
                )
                
                print(f"    ✓ 成功添加分块: {chunk_title}")
                time.sleep(0.5)  # 避免请求过快
                
            except Exception as e:
                print(f"    ✗ 添加分块失败 {chunk_title}: {e}")
                print(f"    错误类型: {type(e).__name__}")
                
                # 尝试不带关键词的版本
                try:
                    simple_content = f"{chunk_title}\n\n{content.strip()}"
                    new_doc.add_chunk(content=simple_content)
                    print(f"    ✓ 成功添加分块(无关键词): {chunk_title}")
                except Exception as e2:
                    print(f"    ✗ 无关键词版本也失败: {e2}")
                    # 继续处理下一个分块
                    continue
    
    def _extract_keywords(self, content: str, title: str, filename: str = '') -> List[str]:
        """
        从内容中提取关键词，优先级策略：
        1. 核心类名/API名（从文件名推断）
        2. 当前二级标题
        3. 从当前chunk中抽取的内容关键词
        """
        keywords = []
        
        # 确保输入参数不为 None
        if content is None:
            content = ''
        if title is None:
            title = ''
        if filename is None:
            filename = ''
        
        # 1. 从文件名提取核心类名/API名
        core_names = self._extract_core_names_from_filename(filename)
        keywords.extend(core_names)
        
        # 2. 添加当前二级标题作为关键词
        if title and title not in keywords:
            keywords.append(title)
        
        # 3. 从内容中提取关键词
        content_keywords = self._extract_content_keywords(content)
        keywords.extend(content_keywords)
        
        # 清理和去重
        cleaned_keywords = []
        for keyword in keywords:
            if keyword is None:
                continue
            keyword = str(keyword).strip()
            if keyword and len(keyword) > 1 and keyword not in cleaned_keywords:
                cleaned_keywords.append(keyword)
        
        return cleaned_keywords[:10]  # 限制关键词数量
    
    def _extract_core_names_from_filename(self, filename: str) -> List[str]:
        """从文件名提取核心类名和API名"""
        core_names = []
        
        if not filename:
            return core_names
        
        # 从文件路径提取信息
        path_parts = filename.split('/')
        
        # 获取文件名（不含扩展名）
        file_base = path_parts[-1].replace('.md', '') if path_parts else ''
        
        # API文件名模式匹配
        api_patterns = [
            r'make_(\w+)_r(\w+)',  # make_box_rsolid -> box, solid
            r'(\w+)_r(\w+)',       # extrude_rsolid -> extrude, solid
            r'(\w+)_(\w+)',        # simple_workplane -> simple, workplane
        ]
        
        for pattern in api_patterns:
            matches = re.findall(pattern, file_base)
            for match in matches:
                core_names.extend([part for part in match if part])
        
        # 直接从文件名提取关键词
        if not core_names:
            # 分割文件名中的单词
            words = re.split(r'[_\-\s]+', file_base)
            core_names.extend([word for word in words if len(word) > 2])
        
        # 添加目录信息作为上下文
        if len(path_parts) > 1:
            directory = path_parts[-2]  # 获取父目录名
            if directory in ['api', 'core']:
                core_names.append(directory)
        
        return core_names[:3]  # 限制核心名称数量
    
    def _extract_content_keywords(self, content: str) -> List[str]:
        """从内容中提取关键词"""
        keywords = []
        
        # 1. 提取类名和函数名
        try:
            # 提取类定义
            class_matches = re.findall(r'class\s+(\w+)', content)
            keywords.extend(class_matches)
            
            # 提取函数定义
            func_matches = re.findall(r'def\s+(\w+)', content)
            keywords.extend(func_matches)
            
            # 提取代码块中的函数调用
            code_blocks = re.findall(r'```python\n(.*?)\n```', content, re.DOTALL)
            for block in code_blocks:
                if block:
                    # 提取函数调用
                    call_matches = re.findall(r'(\w+)\s*\(', block)
                    keywords.extend(call_matches)
        except Exception:
            pass
        
        # 2. 提取API相关关键词
        api_patterns = [
            r'`(\w+)`',                    # 代码片段
            r'- \*\*(\w+)\*\*',           # 粗体参数
            r'### (.*?)(?=\n|$)',         # 三级标题
            r'return\s+(\w+)',            # 返回值类型
            r'(\w+)\s*:\s*(\w+)',         # 参数类型声明
            r'(\w+)\s*=\s*(\w+)',         # 赋值语句
        ]
        
        for pattern in api_patterns:
            try:
                matches = re.findall(pattern, content)
                if isinstance(matches[0], tuple) if matches else False:
                    # 处理元组匹配结果
                    for match_tuple in matches:
                        keywords.extend([item for item in match_tuple if item])
                else:
                    keywords.extend(matches)
            except Exception:
                pass
        
        # 3. 提取重要的术语
        important_terms = [
            'RSolid', 'RFace', 'RWire', 'REdge', 'RVertex',
            'SimpleWorkplane', 'CoordinateSystem', 'Compound',
            'extrude', 'revolve', 'loft', 'sweep', 'fillet', 'chamfer',
            'union', 'cut', 'intersect', 'mirror', 'rotate', 'translate',
            'pattern', 'shell', 'make', 'create', 'build'
        ]
        
        for term in important_terms:
            if term.lower() in content.lower():
                keywords.append(term)
        
        # 4. 提取参数名
        param_matches = re.findall(r'(\w+)\s*:\s*\w+', content)
        keywords.extend(param_matches)
        
        return keywords
    
    def sync_documents(self):
        """同步文档到RAGFlow"""
        print("开始同步SimpleCADAPI文档到RAGFlow...")
        
        # 确保数据集存在
        self._ensure_dataset()

        assert self.dataset is not None, "数据集未初始化，请先调用 _ensure_dataset()"
        
        # 获取所有markdown文件
        md_files = self._get_all_markdown_files()
        print(f"找到 {len(md_files)} 个markdown文件")
        
        updated_count = 0
        
        for md_file in md_files:
            try:
                # 计算文件相对路径作为文档名
                relative_path = md_file.relative_to(self.docs_dir)
                doc_name = str(relative_path)
                
                # 检查文件是否有变化
                current_hash = self._get_file_hash(md_file)
                cached_hash = self.file_hashes.get(doc_name)
                
                if current_hash == cached_hash:
                    print(f"跳过未变化的文件: {doc_name}")
                    continue
                
                print(f"处理文件: {doc_name}")
                
                # 读取文件内容
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # 按二级标题分割
                chunks = self._split_markdown_by_h2(content, doc_name)
                print(f"  分割为 {len(chunks)} 个块")

                for i, chunk in enumerate(chunks):
                    print(f"    块 {i+1}: {chunk['title'][:30]}... ({len(chunk['content'])} 字符)")
                
                # 更新文档
                self._update_document_with_chunks(doc_name, chunks)
                
                # 更新缓存
                self.file_hashes[doc_name] = current_hash
                updated_count += 1
                
                print(f"  ✓ 完成处理: {doc_name}")
                
            except Exception as e:
                print(f"  ✗ 处理文件失败 {md_file}: {e}")
        
        # 保存缓存
        self._save_cache()
        
        print(f"\n同步完成! 共更新了 {updated_count} 个文档")
        
        # 显示数据集信息
        docs = self.dataset.list_documents()
        total_chunks = sum(len(doc.list_chunks()) for doc in docs)
        print(f"数据集 '{self.dataset_name}' 现有 {len(docs)} 个文档，{total_chunks} 个分块")

def main():
    """主函数"""
    # 配置参数
    API_KEY = os.getenv("RAGFLOW_API_KEY", "")
    BASE_URL = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")
    DATASET_NAME = "SimpleCADAPI"
    
    if not API_KEY:
        print("请设置环境变量 RAGFLOW_API_KEY")
        print("例如: export RAGFLOW_API_KEY='your_api_key_here'")
        exit(1)
    
    print(f"RAGFlow服务器: {BASE_URL}")
    print(f"数据集名称: {DATASET_NAME}")
    
    # 创建同步器并运行
    syncer = SimpleCADAPIRAGFlowSync(API_KEY, BASE_URL, DATASET_NAME)
    syncer.sync_documents()

if __name__ == "__main__":
    main()
