# RAGFlow文档同步脚本使用说明

## 简介

这个脚本用于将SimpleCADAPI的文档自动同步到RAGFlow数据库。脚本会：

1. 检查是否存在名为"SimpleCADAPI"的数据集，如果不存在则创建
2. 扫描本地文档目录，检查文档是否有变更
3. 对于有变更的文档，删除旧版本并创建新版本
4. 按照二级标题（##）为单位切分文档为chunks
5. 为每个chunk提取关键词以提高搜索效果

## 安装依赖

```bash
pip install ragflow-sdk
```

## 环境变量设置

在运行脚本之前，需要设置以下环境变量：

```bash
export RAGFLOW_API_KEY="your_ragflow_api_key"
export RAGFLOW_BASE_URL="http://your-ragflow-server:9380"  # 可选，默认为localhost:9380
```

## 使用方法

### 1. 基本使用

```bash
cd /Users/lildino/Project/SimpleCADAPI
python scripts/ragflow_sync.py
```

### 2. 检查脚本是否可执行

```bash
chmod +x scripts/ragflow_sync.py
./scripts/ragflow_sync.py
```

## 脚本功能说明

### 文档变更检测

- 脚本会计算每个文档的MD5哈希值
- 与上次同步时的哈希值比较，只处理有变更的文档
- 哈希值缓存在 `scripts/ragflow_cache.json` 文件中

### 分块策略

脚本按照以下策略切分文档：

1. **按二级标题切分**：以 `## ` 开头的行作为分块边界
2. **保留标题**：每个chunk包含其对应的标题
3. **关键词提取**：自动提取以下关键词：
   - 标题内容
   - 代码块中的函数名
   - API参数名（粗体标记）
   - 其他重要术语

### 错误处理

- 如果文档上传失败，会显示错误信息但不中断整个同步过程
- 网络错误会有重试机制（通过time.sleep实现）

## 示例输出

```
开始同步SimpleCADAPI文档到RAGFlow...
找到已存在的数据集: SimpleCADAPI
找到 45 个markdown文件
跳过未变化的文件: api/README.md
处理文件: api/chamfer_rsolid.md
  分割为 6 个块
  处理文档: api/chamfer_rsolid.md
  删除现有文档: api/chamfer_rsolid.md
  创建新文档: api/chamfer_rsolid.md
  添加 6 个分块
    添加分块: API定义
    添加分块: API作用
    添加分块: API参数说明
    添加分块: 返回值
    添加分块: 异常
    添加分块: API使用例子
  ✓ 完成处理: api/chamfer_rsolid.md

同步完成! 共更新了 12 个文档
数据集 'SimpleCADAPI' 现有 45 个文档，276 个分块
```

## 配置选项

在脚本的main函数中，你可以修改以下配置：

```python
# 数据集名称
DATASET_NAME = "SimpleCADAPI"

# RAGFlow服务器地址
BASE_URL = os.getenv("RAGFLOW_BASE_URL", "http://localhost:9380")
```

## 故障排除

### 1. 连接错误
- 检查RAGFlow服务器是否运行
- 验证BASE_URL是否正确
- 确认网络连接

### 2. 认证错误
- 检查API_KEY是否正确
- 确认API密钥有足够权限

### 3. 文档上传失败
- 检查文档格式是否为有效的markdown
- 确认文档大小不超过限制
- 查看详细错误信息

### 4. 分块问题
- 检查markdown文档是否有正确的二级标题格式
- 确认文档编码为UTF-8

## 定期同步

可以设置定时任务定期运行同步：

```bash
# 添加到crontab，每小时同步一次
0 * * * * cd /Users/lildino/Project/SimpleCADAPI && python scripts/ragflow_sync.py >> /var/log/ragflow_sync.log 2>&1
```

## 注意事项

1. 首次运行会处理所有文档，可能需要较长时间
2. 脚本会自动处理重复文档，删除旧版本
3. 建议在非高峰时间运行，避免影响RAGFlow服务性能
4. 定期备份ragflow_cache.json文件，避免重复处理未变更的文档
